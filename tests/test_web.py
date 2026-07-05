import os
from datetime import date, timedelta
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
        self.assertIn("この先で見えること", index.text)
        self.assertIn("相手の本音と次の一手を見る", index.text)
        self.assertIn("プレミアム鑑定 500円", index.text)
        self.assertIn("生年月日", index.text)
        self.assertIn("数秘術や星座の要素", index.text)
        app_js = self.client.get("/static/app.js")
        self.assertEqual(app_js.status_code, 200)
        for label in (
            "相手の本音と次の一手を見る",
            "復縁の可能性を深く見る",
            "二人の相性を詳しく見る",
            "今の仕事運と次の一手を見る",
            "今日の流れを詳しく見る",
        ):
            self.assertIn(label, app_js.text)
        self.assertNotIn("500円で", app_js.text)
        self.assertIn("連絡すべきか、もう少し待つべきか", app_js.text)
        self.assertIn("残すべき強みや収入の芽", app_js.text)
        self.assertIn("生年月日から見た、仕事で力を活かしやすい方向", app_js.text)
        self.assertIn('replaceAll("/", "-")', app_js.text)
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

    @patch("src.kimidake_bot.web.get_generator")
    def test_fortune_accepts_valid_birthday(self, get_generator):
        generator = Mock()
        generator.generate.return_value = "生年月日ありの鑑定結果"
        get_generator.return_value = (generator, self.settings)

        response = self.client.post(
            "/api/fortune",
            json={
                "nickname": "あおい",
                "birthday": "2000-11-22",
                "category": "work",
                "concern": "副業を続けるか迷っています",
            },
        )

        self.assertEqual(response.status_code, 200)
        fortune_input = generator.generate.call_args.args[0]
        self.assertEqual(fortune_input.birthday, date(2000, 11, 22))

    @patch("src.kimidake_bot.web.get_generator")
    def test_slash_birthday_is_normalized_and_reaches_handler(self, get_generator):
        generator = Mock()
        generator.generate.return_value = "スラッシュ形式の鑑定結果"
        get_generator.return_value = (generator, self.settings)

        response = self.client.post(
            "/api/fortune",
            json={
                "nickname": "あおい",
                "birthday": "2000/11/22",
                "category": "work",
                "concern": "やる気の波が激しいです",
            },
        )

        self.assertEqual(response.status_code, 200)
        fortune_input = generator.generate.call_args.args[0]
        self.assertEqual(fortune_input.birthday.isoformat(), "2000-11-22")

    @patch("src.kimidake_bot.web.get_generator")
    def test_fortune_without_birthday_remains_valid(self, get_generator):
        generator = Mock()
        generator.generate.return_value = "生年月日なしの鑑定結果"
        get_generator.return_value = (generator, self.settings)

        response = self.client.post(
            "/api/fortune",
            json={"birthday": "", "category": "work", "concern": "仕事の悩み"},
        )

        self.assertEqual(response.status_code, 200)
        fortune_input = generator.generate.call_args.args[0]
        self.assertIsNone(fortune_input.birthday)

    def test_invalid_birthday_is_rejected_before_generator(self):
        invalid_birthdays = ("2000.11.22", "2024-02-30", "not-a-date")
        for birthday in invalid_birthdays:
            with self.subTest(birthday=birthday):
                with patch("src.kimidake_bot.web.get_generator") as get_generator:
                    response = self.client.post(
                        "/api/fortune",
                        json={"birthday": birthday, "category": "work", "concern": "仕事の悩み"},
                    )
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("生年月日", response.json()["error"])
                    get_generator.assert_not_called()

    def test_future_birthday_is_rejected_before_generator(self):
        future = (date.today() + timedelta(days=1)).isoformat()
        with patch("src.kimidake_bot.web.get_generator") as get_generator:
            response = self.client.post(
                "/api/fortune",
                json={"birthday": future, "category": "work", "concern": "仕事の悩み"},
            )
            self.assertEqual(response.status_code, 400)
            get_generator.assert_not_called()

    def test_birthday_older_than_120_years_is_rejected(self):
        too_old = date(date.today().year - 121, 1, 1).isoformat()
        with patch("src.kimidake_bot.web.get_generator") as get_generator:
            response = self.client.post(
                "/api/fortune",
                json={"birthday": too_old, "category": "work", "concern": "仕事の悩み"},
            )
            self.assertEqual(response.status_code, 400)
            get_generator.assert_not_called()

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
        user_prompt = llm.generate_fortune.call_args.kwargs["user_prompt"]
        system_prompt = llm.generate_fortune.call_args.kwargs["system_prompt"]
        self.assertIn("転職すべきか", user_prompt)
        self.assertIn("選択した自分への疑い", user_prompt)
        self.assertIn("心がどこを痛めているか", user_prompt)
        self.assertIn("感情の見抜きを十分に言葉にする前に", user_prompt)
        self.assertIn("必ず4段落", system_prompt)
        self.assertIn("今いちばん避けたいこと", system_prompt)
        self.assertIn("ここから先で見えてくるのは", system_prompt)
        self.assertIn("購入、価格、有料鑑定という言葉は本文に出さない", system_prompt)
        self.assertIn("未来、成功、復縁、収入", system_prompt)
        self.assertNotIn("生年月日:", user_prompt)
        combined_prompt = system_prompt + user_prompt
        for phrase in (
            "生年月日はないので",
            "生年月日が入力されていないため",
            "断定はしませんが",
            "情報が少ないので",
        ):
            self.assertNotIn(phrase, combined_prompt)

    def test_generator_adds_birth_profile_to_prompt(self):
        llm = Mock()
        llm.generate_fortune.return_value = "生年月日を使った鑑定結果"
        generator = WebFortuneGenerator(Path("src/kimidake_bot/prompts"), llm)

        with self.assertLogs("uvicorn.error", level="INFO") as captured:
            generator.generate(
                WebFortuneInput(
                    category="work",
                    concern="副業を諦めそうです",
                    nickname="あおい",
                    birthday=date(2000, 11, 22),
                ),
                settings=self.settings,
            )

        user_prompt = llm.generate_fortune.call_args.kwargs["user_prompt"]
        diagnostic_log = "\n".join(captured.output)
        self.assertIn("生年月日: 2000-11-22", user_prompt)
        self.assertIn("星座: 蠍座", user_prompt)
        self.assertIn("星座由来の読みの足場", user_prompt)
        self.assertIn("別の可能性まで探したくなる", user_prompt)
        self.assertIn("ライフパスナンバー: 8", user_prompt)
        self.assertIn("数秘術由来の読みの足場", user_prompt)
        self.assertIn("現実の成果や形につなげたい", user_prompt)
        self.assertIn("2つの読みの足場を両方使い", user_prompt)
        system_prompt = llm.generate_fortune.call_args.kwargs["system_prompt"]
        self.assertIn("生年月日を反映したと読者が分かる", system_prompt)
        self.assertIn("birthdate_present=true", diagnostic_log)
        self.assertIn("zodiac_calculated=true", diagnostic_log)
        self.assertIn("life_path_calculated=true", diagnostic_log)
        self.assertNotIn("2000-11-22", diagnostic_log)

    def test_missing_birthday_logs_only_false_flags(self):
        llm = Mock()
        llm.generate_fortune.return_value = "相談内容だけを使った鑑定結果"
        generator = WebFortuneGenerator(Path("src/kimidake_bot/prompts"), llm)

        with self.assertLogs("uvicorn.error", level="INFO") as captured:
            generator.generate(
                WebFortuneInput(category="work", concern="SECRET_CONCERN"),
                settings=self.settings,
            )

        diagnostic_log = "\n".join(captured.output)
        self.assertIn("birthdate_present=false", diagnostic_log)
        self.assertIn("zodiac_calculated=false", diagnostic_log)
        self.assertIn("life_path_calculated=false", diagnostic_log)
        self.assertNotIn("SECRET_CONCERN", diagnostic_log)

    def test_forbidden_birthdate_disclaimers_are_removed_from_output(self):
        llm = Mock()
        llm.generate_fortune.return_value = (
            "生年月日はないので断定はしませんが、一般的にお伝えします。\n\n"
            "今は流れを整える時期です。\n\n"
            "今日は15分だけ着手してください。"
        )
        generator = WebFortuneGenerator(Path("src/kimidake_bot/prompts"), llm)

        result = generator.generate(
            WebFortuneInput(category="work", concern="仕事の悩み"),
            settings=self.settings,
        )

        self.assertNotIn("生年月日はないので", result)
        self.assertNotIn("断定はしませんが", result)
        self.assertIn("今は流れを整える時期です", result)

    def test_mock_result_matches_four_paragraph_structure(self):
        self.assertEqual(len(MOCK_FORTUNE_RESULT.split("\n\n")), 4)
        self.assertIn("選んできた自分", MOCK_FORTUNE_RESULT)
        self.assertIn("停滞期", MOCK_FORTUNE_RESULT)
        final_paragraph = MOCK_FORTUNE_RESULT.split("\n\n")[-1]
        self.assertIn("ここから先で見えてくるのは", final_paragraph)
        for phrase in ("紙に書いて", "メモして", "15分", "書き出して", "整理して"):
            self.assertNotIn(phrase, final_paragraph)

    def test_heavy_do_ending_is_replaced_with_category_continuation(self):
        llm = Mock()
        llm.generate_fortune.return_value = (
            "今の状態です。\n\n"
            "今の流れです。\n\n"
            "避けたいことです。\n\n"
            "最後に紙に書いて15分やってください。"
        )
        generator = WebFortuneGenerator(Path("src/kimidake_bot/prompts"), llm)

        result = generator.generate(
            WebFortuneInput(category="work", concern="仕事の悩み"),
            settings=self.settings,
        )

        final_paragraph = result.split("\n\n")[-1]
        self.assertNotIn("紙に書いて", final_paragraph)
        self.assertNotIn("15分", final_paragraph)
        self.assertIn("残すべき強み", final_paragraph)

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
