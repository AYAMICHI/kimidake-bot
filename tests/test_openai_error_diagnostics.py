import httpx
from unittest import TestCase

from openai import BadRequestError

from src.kimidake_bot.services.openai_error_diagnostics import (
    log_openai_bad_request,
)


def make_bad_request(body: dict) -> BadRequestError:
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    response = httpx.Response(400, request=request)
    return BadRequestError("Error code: 400", response=response, body=body)


class OpenAIBadRequestDiagnosticsTest(TestCase):
    def test_logs_allowed_nested_error_fields_and_redacts_sensitive_values(self):
        api_key = "sk-project-secret-value"
        concern = "秘密の悩み本文"
        birthdate = "2000-11-22"
        result = "秘密の無料鑑定結果"
        error = make_bad_request(
            {
                "error": {
                    "code": "unsupported_parameter",
                    "param": "temperature",
                    "message": (
                        "Unsupported parameter temperature "
                        f"input={concern} birthdate={birthdate} result={result} key={api_key}"
                    ),
                    "type": "invalid_request_error",
                }
            }
        )

        with self.assertLogs("uvicorn.error", level="WARNING") as captured:
            log_openai_bad_request(
                error,
                sensitive_values=(api_key, concern, birthdate, result),
            )

        log_text = "\n".join(captured.output)
        self.assertIn("status_code=400", log_text)
        self.assertIn("error_code=unsupported_parameter", log_text)
        self.assertIn("rejected_parameter=temperature", log_text)
        self.assertIn("error_message=Unsupported parameter temperature", log_text)
        self.assertNotIn(api_key, log_text)
        self.assertNotIn(concern, log_text)
        self.assertNotIn(birthdate, log_text)
        self.assertNotIn(result, log_text)

    def test_supports_top_level_sdk_error_body(self):
        error = make_bad_request(
            {
                "code": "model_not_found",
                "param": "model",
                "message": "The requested model is unavailable",
                "type": "invalid_request_error",
            }
        )

        with self.assertLogs("uvicorn.error", level="WARNING") as captured:
            log_openai_bad_request(error)

        log_text = "\n".join(captured.output)
        self.assertIn("error_code=model_not_found", log_text)
        self.assertIn("rejected_parameter=model", log_text)
        self.assertIn("error_message=The requested model is unavailable", log_text)
