from datetime import date
import os
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
import httpx
from openai import BadRequestError

from src.kimidake_bot import web
from src.kimidake_bot.logic.premium_fortune import (
    FREE_RESULT_CONTEXT_MAX_CHARS,
    PremiumFortuneGenerator,
    PremiumFortuneResult,
)
from src.kimidake_bot.logic.web_fortune import WebFortuneInput
from src.kimidake_bot.rate_limit import InMemoryRateLimiter
from src.kimidake_bot.services.generation_result import GenerationResult, UsageSummary


class PremiumFortuneGeneratorTest(TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(
            model_premium="test-premium-model",
            max_output_tokens_premium=1800,
            temperature=0.85,
        )

    def test_uses_premium_model_output_limit_birth_profile_and_free_result(self):
        llm = Mock()
        llm.generate_fortune_with_metadata.return_value = GenerationResult(
            text="【鑑定の総論】\n深い鑑定結果",
            model="test-premium-model",
            usage=UsageSummary(100, 200, 300),
            estimated_cost_usd="0.00650000",
        )
        generator = PremiumFortuneGenerator(Path("src/kimidake_bot/prompts"), llm)

        result = generator.generate(
            WebFortuneInput(
                nickname="あおい",
                birthday=date(2000, 11, 22),
                category="work",
                concern="副業を続けるか迷っています",
            ),
            free_result="無料鑑定で見えた核心",
            settings=self.settings,
        )

        request = llm.generate_fortune_with_metadata.call_args.kwargs
        self.assertEqual(request["model"], "test-premium-model")
        self.assertEqual(request["max_output_tokens"], 1800)
        self.assertIn("星座: 蠍座", request["user_prompt"])
        self.assertIn("ライフパスナンバー: 8", request["user_prompt"])
        self.assertIn("無料鑑定で見えた核心", request["user_prompt"])
        self.assertEqual(result.usage.total_tokens, 300)
        self.assertEqual(result.estimated_cost_usd, "0.00650000")

    def test_without_birthdate_does_not_mention_missing_birth_information(self):
        llm = Mock()
        llm.generate_fortune_with_metadata.return_value = GenerationResult(
            text="【鑑定の総論】\n相談内容だけで自然に深掘りします。",
            model="test-premium-model",
        )
        generator = PremiumFortuneGenerator(Path("src/kimidake_bot/prompts"), llm)

        generator.generate(
            WebFortuneInput(category="love", concern="距離感に迷っています"),
            free_result=None,
            settings=self.settings,
        )

        prompt = llm.generate_fortune_with_metadata.call_args.kwargs["user_prompt"]
        self.assertNotIn("出生情報ブロック", prompt)
        self.assertNotIn("生年月日はない", prompt)
        self.assertNotIn("情報が少ない", prompt)

    def test_free_result_context_is_truncated_and_sensitive_values_are_not_logged(self):
        concern = "LOGに残してはいけない悩み"
        birthday = date(2000, 11, 22)
        llm = Mock()
        llm.generate_fortune_with_metadata.return_value = GenerationResult(
            text="LOGに残してはいけないAI出力",
            model="test-premium-model",
        )
        generator = PremiumFortuneGenerator(Path("src/kimidake_bot/prompts"), llm)

        with self.assertLogs("uvicorn.error", level="INFO") as captured:
            generator.generate(
                WebFortuneInput(
                    category="work", concern=concern, birthday=birthday
                ),
                free_result="x" * (FREE_RESULT_CONTEXT_MAX_CHARS + 500),
                settings=self.settings,
            )

        prompt = llm.generate_fortune_with_metadata.call_args.kwargs["user_prompt"]
        self.assertIn("x" * FREE_RESULT_CONTEXT_MAX_CHARS, prompt)
        self.assertNotIn("x" * (FREE_RESULT_CONTEXT_MAX_CHARS + 1), prompt)
        log_text = "\n".join(captured.output)
        self.assertIn("birthdate_present=true", log_text)
        self.assertNotIn(concern, log_text)
        self.assertNotIn("2000-11-22", log_text)
        self.assertNotIn("LOGに残してはいけないAI出力", log_text)


class PremiumFortuneApiTest(TestCase):
    def setUp(self):
        web.rate_limiter = InMemoryRateLimiter(max_requests=3, window_seconds=60)
        self.client = TestClient(web.app)
        self.settings = SimpleNamespace(
            enable_premium_preview=True,
            max_input_chars_premium=1200,
            request_timeout_seconds=1,
            openai_api_key="sk-test-secret-key",
        )

    def payload(self, **overrides):
        payload = {
            "nickname": "あおい",
            "category": "work",
            "concern": "副業を続けるか迷っています",
            "birthdate": "2000/11/22",
            "free_result": "無料鑑定の続き",
        }
        payload.update(overrides)
        return payload

    def test_preview_ui_is_marked_enabled_only_when_flag_is_true(self):
        with patch("src.kimidake_bot.web.premium_preview_enabled", return_value=True):
            enabled = self.client.get("/")
        with patch("src.kimidake_bot.web.premium_preview_enabled", return_value=False):
            disabled = self.client.get("/")

        self.assertIn('data-premium-preview-enabled="true"', enabled.text)
        self.assertIn("開発用プレビュー", enabled.text)
        self.assertIn('data-premium-preview-enabled="false"', disabled.text)
        self.assertNotIn("開発用プレビュー", disabled.text)

    @patch("src.kimidake_bot.web.get_premium_generator")
    @patch("src.kimidake_bot.web.premium_preview_enabled", return_value=False)
    def test_disabled_preview_rejects_api(self, _enabled, get_generator):
        response = self.client.post("/api/premium-fortune", json=self.payload())

        self.assertEqual(response.status_code, 403)
        get_generator.assert_not_called()

    @patch("src.kimidake_bot.web.premium_preview_enabled", return_value=True)
    def test_enabled_preview_returns_result_usage_and_cost(self, _enabled):
        generator = Mock()
        generator.generate.return_value = PremiumFortuneResult(
            result="プレミアム鑑定結果",
            model="test-premium-model",
            usage=UsageSummary(111, 222, 333),
            estimated_cost_usd="0.00721500",
        )
        with patch(
            "src.kimidake_bot.web.get_premium_generator",
            return_value=(generator, self.settings),
        ):
            response = self.client.post("/api/premium-fortune", json=self.payload())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"], "プレミアム鑑定結果")
        self.assertEqual(response.json()["usage"]["total_tokens"], 333)
        self.assertEqual(response.json()["estimated_cost_usd"], "0.00721500")
        fortune_input = generator.generate.call_args.args[0]
        self.assertEqual(fortune_input.birthday.isoformat(), "2000-11-22")
        self.assertEqual(
            generator.generate.call_args.kwargs["free_result"], "無料鑑定の続き"
        )

    @patch("src.kimidake_bot.web.premium_preview_enabled", return_value=True)
    def test_premium_input_limit_rejects_before_generation(self, _enabled):
        generator = Mock()
        with patch(
            "src.kimidake_bot.web.get_premium_generator",
            return_value=(generator, self.settings),
        ):
            response = self.client.post(
                "/api/premium-fortune",
                json=self.payload(concern="あ" * 1201),
            )

        self.assertEqual(response.status_code, 400)
        generator.generate.assert_not_called()

    def test_mock_preview_works_without_api_key_or_openai_client(self):
        mock_env = {
            "OPENAI_API_KEY": "",
            "USE_MOCK_AI": "true",
            "ENABLE_PREMIUM_PREVIEW": "true",
            "OPENAI_MODEL_FREE": "test-free",
            "OPENAI_MODEL_PREMIUM": "test-premium",
            "MAX_INPUT_CHARS_FREE": "400",
            "MAX_OUTPUT_TOKENS_FREE": "500",
            "MAX_INPUT_CHARS_PREMIUM": "1200",
            "MAX_OUTPUT_TOKENS_PREMIUM": "1800",
        }
        web.get_generator.cache_clear()
        try:
            with (
                patch.dict(os.environ, mock_env, clear=False),
                patch("src.kimidake_bot.web.OpenAITextClient") as openai_client,
            ):
                response = self.client.post(
                    "/api/premium-fortune", json=self.payload()
                )

            self.assertEqual(response.status_code, 200)
            self.assertIn("【鑑定の総論】", response.json()["result"])
            self.assertIsNone(response.json()["usage"])
            openai_client.assert_not_called()
        finally:
            web.get_generator.cache_clear()

    @patch("src.kimidake_bot.web.premium_preview_enabled", return_value=True)
    def test_bad_request_logs_safe_diagnostics(self, _enabled):
        request = httpx.Request("POST", "https://api.openai.com/v1/responses")
        response = httpx.Response(400, request=request)
        bad_request = BadRequestError(
            "Error code: 400",
            response=response,
            body={
                "error": {
                    "code": "unsupported_parameter",
                    "param": "temperature",
                    "message": "Unsupported parameter: temperature",
                }
            },
        )
        generator = Mock()
        generator.generate.side_effect = bad_request

        with (
            patch(
                "src.kimidake_bot.web.get_premium_generator",
                return_value=(generator, self.settings),
            ),
            self.assertLogs("uvicorn.error", level="WARNING") as captured,
        ):
            api_response = self.client.post(
                "/api/premium-fortune", json=self.payload()
            )

        self.assertEqual(api_response.status_code, 503)
        log_text = "\n".join(captured.output)
        self.assertIn("error_code=unsupported_parameter", log_text)
        self.assertIn("rejected_parameter=temperature", log_text)
        self.assertNotIn(self.payload()["concern"], log_text)
        self.assertNotIn(self.payload()["birthdate"], log_text)
        self.assertNotIn(self.payload()["free_result"], log_text)
        self.assertNotIn(self.settings.openai_api_key, log_text)
