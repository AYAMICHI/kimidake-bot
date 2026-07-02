import os
from dataclasses import dataclass
from dotenv import load_dotenv

@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    model_free: str
    model_premium: str | None = None
    max_output_tokens: int = 420
    # miniは少し高めの方が人間っぽくなる
    temperature: float = 0.85  # “自然さ”を出しつつ暴れすぎない
    request_timeout_seconds: float = 25.0

    @property
    def model_default(self) -> str:
        """既存CLIとの互換性を保つための別名。"""
        return self.model_free

def get_settings() -> Settings:
    load_dotenv()  # .env を読む（ローカル用）
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is missing. Set it in .env or environment variables.")
    model_free = os.getenv("OPENAI_MODEL_FREE")
    if not model_free:
        raise RuntimeError("OPENAI_MODEL_FREE is missing. Set it in .env or environment variables.")
    return Settings(
        openai_api_key=key,
        model_free=model_free,
        model_premium=os.getenv("OPENAI_MODEL_PREMIUM") or None,
    )
