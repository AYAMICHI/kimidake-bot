import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()  # .env を読む（ローカル用）

@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    model: str = "gpt-5.2"
    max_output_tokens: int = 420
    temperature: float = 0.8  # “自然さ”を出しつつ暴れすぎない

def get_settings() -> Settings:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is missing. Set it in .env or environment variables.")
    return Settings(openai_api_key=key)
