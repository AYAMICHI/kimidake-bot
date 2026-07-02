import os
from dataclasses import dataclass
from dotenv import load_dotenv

@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    use_mock_ai: bool
    model_free: str
    model_premium: str
    max_input_chars_free: int
    max_output_tokens_free: int
    max_input_chars_premium: int
    max_output_tokens_premium: int
    # miniは少し高めの方が人間っぽくなる
    temperature: float = 0.85  # “自然さ”を出しつつ暴れすぎない
    request_timeout_seconds: float = 25.0

    @property
    def model_default(self) -> str:
        """既存CLIとの互換性を保つための別名。"""
        return self.model_free

    @property
    def max_output_tokens(self) -> int:
        """既存CLIとの互換性を保つための別名。"""
        return self.max_output_tokens_free


def _required_positive_int(name: str) -> int:
    raw = os.getenv(name)
    if not raw:
        raise RuntimeError(f"{name} is missing. Set it in .env or environment variables.")
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be greater than zero.")
    return value


def _optional_bool(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise RuntimeError(f"{name} must be true or false.")

def get_settings() -> Settings:
    load_dotenv()  # .env を読む（ローカル用）
    use_mock_ai = _optional_bool("USE_MOCK_AI")
    key = os.getenv("OPENAI_API_KEY")
    if not key and not use_mock_ai:
        raise RuntimeError("OPENAI_API_KEY is missing. Set it in .env or environment variables.")
    model_free = os.getenv("OPENAI_MODEL_FREE")
    if not model_free:
        raise RuntimeError("OPENAI_MODEL_FREE is missing. Set it in .env or environment variables.")
    model_premium = os.getenv("OPENAI_MODEL_PREMIUM")
    if not model_premium:
        raise RuntimeError("OPENAI_MODEL_PREMIUM is missing. Set it in .env or environment variables.")
    return Settings(
        openai_api_key=key,
        use_mock_ai=use_mock_ai,
        model_free=model_free,
        model_premium=model_premium,
        max_input_chars_free=_required_positive_int("MAX_INPUT_CHARS_FREE"),
        max_output_tokens_free=_required_positive_int("MAX_OUTPUT_TOKENS_FREE"),
        max_input_chars_premium=_required_positive_int("MAX_INPUT_CHARS_PREMIUM"),
        max_output_tokens_premium=_required_positive_int("MAX_OUTPUT_TOKENS_PREMIUM"),
    )
