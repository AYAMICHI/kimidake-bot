from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

from src.kimidake_bot.services.openai_client import OpenAITextClient


class OpenAITextClientTest(TestCase):
    def test_logs_response_usage_without_prompt_or_output(self):
        response = SimpleNamespace(
            model="gpt-5.4-mini-2026-03-17",
            output_text="SECRET_AI_OUTPUT",
            usage=SimpleNamespace(
                input_tokens=1000,
                output_tokens=500,
                total_tokens=1500,
                input_tokens_details=SimpleNamespace(cached_tokens=200),
            ),
        )
        sdk_client = Mock()
        sdk_client.responses.create.return_value = response
        client = OpenAITextClient.__new__(OpenAITextClient)
        client.client = sdk_client

        with self.assertLogs("uvicorn.error", level="INFO") as captured:
            result = client.generate_fortune(
                model="gpt-5.4-mini",
                system_prompt="SECRET_SYSTEM_PROMPT",
                user_prompt="SECRET_USER_CONCERN birthday=2000-11-22",
                max_output_tokens=500,
                temperature=0.85,
            )

        log_text = "\n".join(captured.output)
        self.assertEqual(result, "SECRET_AI_OUTPUT")
        self.assertIn("model=gpt-5.4-mini-2026-03-17", log_text)
        self.assertIn("input_tokens=1000", log_text)
        self.assertIn("output_tokens=500", log_text)
        self.assertIn("total_tokens=1500", log_text)
        self.assertIn("estimated_cost_usd=0.00286500", log_text)
        self.assertNotIn("SECRET_SYSTEM_PROMPT", log_text)
        self.assertNotIn("SECRET_USER_CONCERN", log_text)
        self.assertNotIn("2000-11-22", log_text)
        self.assertNotIn("SECRET_AI_OUTPUT", log_text)

    def test_unknown_model_reports_unknown_cost(self):
        response = SimpleNamespace(
            model="custom-model",
            output_text="result",
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=20,
                total_tokens=30,
                input_tokens_details=None,
            ),
        )
        sdk_client = Mock()
        sdk_client.responses.create.return_value = response
        client = OpenAITextClient.__new__(OpenAITextClient)
        client.client = sdk_client

        with self.assertLogs("uvicorn.error", level="INFO") as captured:
            client.generate_fortune(
                model="custom-model",
                system_prompt="system",
                user_prompt="user",
                max_output_tokens=100,
                temperature=0.5,
            )

        self.assertIn("estimated_cost_usd=unknown", "\n".join(captured.output))

    def test_metadata_result_exposes_usage_and_estimated_cost(self):
        response = SimpleNamespace(
            model="gpt-5.5",
            output_text="premium result",
            usage=SimpleNamespace(
                input_tokens=100,
                output_tokens=200,
                total_tokens=300,
                input_tokens_details=SimpleNamespace(cached_tokens=0),
            ),
        )
        sdk_client = Mock()
        sdk_client.responses.create.return_value = response
        client = OpenAITextClient.__new__(OpenAITextClient)
        client.client = sdk_client

        result = client.generate_fortune_with_metadata(
            model="gpt-5.5",
            system_prompt="system",
            user_prompt="user",
            max_output_tokens=1800,
            temperature=0.85,
        )

        self.assertEqual(result.usage.input_tokens, 100)
        self.assertEqual(result.usage.output_tokens, 200)
        self.assertEqual(result.usage.total_tokens, 300)
        self.assertEqual(result.estimated_cost_usd, "0.00650000")
        self.assertEqual(
            sdk_client.responses.create.call_args.kwargs["max_output_tokens"], 1800
        )

    def test_gpt_5_5_request_omits_sampling_parameters(self):
        response = SimpleNamespace(model="gpt-5.5", output_text="result", usage=None)
        sdk_client = Mock()
        sdk_client.responses.create.return_value = response
        client = OpenAITextClient.__new__(OpenAITextClient)
        client.client = sdk_client

        client.generate_fortune_with_metadata(
            model="gpt-5.5",
            system_prompt="system",
            user_prompt="user",
            max_output_tokens=1800,
            temperature=0.85,
        )

        request = sdk_client.responses.create.call_args.kwargs
        self.assertEqual(request["model"], "gpt-5.5")
        self.assertEqual(request["max_output_tokens"], 1800)
        self.assertNotIn("temperature", request)
        self.assertNotIn("top_p", request)

    def test_gpt_5_4_mini_request_keeps_existing_temperature_parameter(self):
        response = SimpleNamespace(
            model="gpt-5.4-mini", output_text="result", usage=None
        )
        sdk_client = Mock()
        sdk_client.responses.create.return_value = response
        client = OpenAITextClient.__new__(OpenAITextClient)
        client.client = sdk_client

        client.generate_fortune_with_metadata(
            model="gpt-5.4-mini",
            system_prompt="system",
            user_prompt="user",
            max_output_tokens=500,
            temperature=0.85,
        )

        request = sdk_client.responses.create.call_args.kwargs
        self.assertEqual(request["model"], "gpt-5.4-mini")
        self.assertEqual(request["max_output_tokens"], 500)
        self.assertEqual(request["temperature"], 0.85)
        self.assertNotIn("top_p", request)
