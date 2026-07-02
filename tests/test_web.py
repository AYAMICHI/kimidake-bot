import os
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from src.kimidake_bot import web
from src.kimidake_bot.config import get_settings
from src.kimidake_bot.logic.web_fortune import WebFortuneGenerator, WebFortuneInput
from src.kimidake_bot.rate_limit import InMemoryRateLimiter
from src.kimidake_bot.services.mock_ai_client import MOCK_FORTUNE_RESULT


class FakeGenerator:
    def generate(self, fortune_input, *, settings):
        return f"{fortune_input.nickname or '相談者'}さんへの鑑定結果"


class WebAppTest(TestCase):
    def setUp(self):
        web.rate_limiter = InMemoryRateLimiter(max_requests=3, window_seconds=60)
        self.client = TestClient(web.app)
        self.settings = SimpleNamespace(
            openai_api_key="test-key",
            use_mock_ai=False,
            model_free="test-model",
            request_timeout_seconds=1,
            max_input_chars_free=400,
            max_output_tokens_free=500,
            temperature=0.85,
        )

    def test_index_and_legal_pages(self):
        index = self.client.get("/")
        self.assertEqual(index.status_code, 200)
        self.assertIn("500円で深く占う", index.text)
        self.assertIn("相手の本音、今後の流れ", index.text)
        for path in ("/terms", "/privacy", "/tokusho", "/contact", "/premium"):
            self.assertEqual(self.client.get(path).status_code, 200)

    @patch("src.kimidake_bot.web.get_generator")
    def test_fortune_success(self, get_generator):
        get_generator.return_value = (FakeGenerator(), self.settings)
        response = self.client.post(
            "/api/fortune",
            json={"nickname": "あおい", "category": "love", "concern": "恋愛の悩み"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["error"], None)
        self.assertIn("あおい", response.json()["result"])

    def test_invalid_input_returns_api_error_shape(self):
        response = self.client.post(
            "/api/fortune",
            json={"category": "invalid", "concern": ""},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["result"], "")
        self.assertIsNotNone(response.json()["error"])

    @patch("src.kimidake_bot.web.get_generator")
    def test_crisis_concern_does_not_call_openai(self, get_generator):
        generator = Mock()
        get_generator.return_value = (generator, self.settings)
        response = self.client.post(
            "/api/fortune",
            json={"category": "work", "concern": "もう死にたい"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("安全", response.json()["result"])
        generator.generate.assert_not_called()

    @patch("src.kimidake_bot.web.get_generator")
    def test_free_input_limit(self, get_generator):
        generator = Mock()
        get_generator.return_value = (generator, self.settings)
        response = self.client.post(
            "/api/fortune",
            json={"category": "love", "concern": "あ" * 401},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("400文字以内", response.json()["error"])
        generator.generate.assert_not_called()

    @patch("src.kimidake_bot.web.get_generator")
    def test_rate_limit(self, get_generator):
        get_generator.return_value = (FakeGenerator(), self.settings)
        payload = {"category": "today", "concern": "今日について知りたい"}
        for _ in range(3):
            self.assertEqual(self.client.post("/api/fortune", json=payload).status_code, 200)
        response = self.client.post("/api/fortune", json=payload)
        self.assertEqual(response.status_code, 429)
        self.assertIsNotNone(response.json()["error"])

    def test_generator_uses_free_output_limit(self):
        llm = Mock()
        llm.generate_fortune.return_value = "短く具体的な鑑定結果"
        generator = WebFortuneGenerator(
            Path("src/kimidake_bot/prompts"),
            llm,
        )
        generator.generate(
            WebFortuneInput(category="work", concern="転職すべきか迷っています"),
            settings=self.settings,
        )
        self.assertEqual(llm.generate_fortune.call_args.kwargs["max_output_tokens"], 500)
        self.assertIn("転職すべきか", llm.generate_fortune.call_args.kwargs["user_prompt"])

    def test_mock_mode_does_not_construct_openai_client(self):
        mock_settings = SimpleNamespace(**vars(self.settings))
        mock_settings.use_mock_ai = True
        mock_settings.openai_api_key = None

        web.get_generator.cache_clear()
        try:
            with (
                patch("src.kimidake_bot.web.get_settings", return_value=mock_settings),
                patch("src.kimidake_bot.web.OpenAITextClient") as openai_client,
            ):
                generator, settings = web.get_generator()
                result = generator.generate(
                    WebFortuneInput(category="love", concern="画面確認用の相談"),
                    settings=settings,
                )
                openai_client.assert_not_called()
                self.assertEqual(result, MOCK_FORTUNE_RESULT)
        finally:
            web.get_generator.cache_clear()

    def test_mock_mode_api_works_without_api_key(self):
        mock_env = {
            "OPENAI_API_KEY": "",
            "USE_MOCK_AI": "true",
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
                    "/api/fortune",
                    json={"category": "love", "concern": "画面確認用の相談"},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["result"], MOCK_FORTUNE_RESULT)
                openai_client.assert_not_called()
        finally:
            web.get_generator.cache_clear()

    def test_real_mode_keeps_openai_client_path(self):
        fake_client = Mock()
        fake_client.generate_fortune.return_value = "実通信経路のテスト結果"

        web.get_generator.cache_clear()
        try:
            with (
                patch("src.kimidake_bot.web.get_settings", return_value=self.settings),
                patch(
                    "src.kimidake_bot.web.OpenAITextClient",
                    return_value=fake_client,
                ) as openai_client,
            ):
                generator, settings = web.get_generator()
                result = generator.generate(
                    WebFortuneInput(category="work", concern="通常経路の確認"),
                    settings=settings,
                )
                openai_client.assert_called_once_with(api_key="test-key", timeout=1)
                fake_client.generate_fortune.assert_called_once()
                self.assertEqual(result, "実通信経路のテスト結果")
        finally:
            web.get_generator.cache_clear()

    def test_use_mock_ai_environment_true_and_false(self):
        base_env = {
            "OPENAI_API_KEY": "test-key",
            "OPENAI_MODEL_FREE": "test-free",
            "OPENAI_MODEL_PREMIUM": "test-premium",
            "MAX_INPUT_CHARS_FREE": "400",
            "MAX_OUTPUT_TOKENS_FREE": "500",
            "MAX_INPUT_CHARS_PREMIUM": "1200",
            "MAX_OUTPUT_TOKENS_PREMIUM": "1800",
        }
        with patch.dict(os.environ, {**base_env, "USE_MOCK_AI": "true"}, clear=False):
            self.assertTrue(get_settings().use_mock_ai)
        with patch.dict(os.environ, {**base_env, "USE_MOCK_AI": "false"}, clear=False):
            self.assertFalse(get_settings().use_mock_ai)
        with (
            patch("src.kimidake_bot.config.load_dotenv"),
            patch.dict(os.environ, base_env, clear=True),
        ):
            self.assertFalse(get_settings().use_mock_ai)


if __name__ == "__main__":
    import unittest

    unittest.main()
