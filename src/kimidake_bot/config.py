import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()  # .env を読む（ローカル用）

@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    # 通常鑑定（MVP・無料・検証用）
    model_default: str = "gpt-4.1-mini"
    # 特別鑑定（将来の有料・深掘り用）
    model_premium: str = "gpt-5.2"
    max_output_tokens: int = 420
    # miniは少し高めの方が人間っぽくなる
    temperature: float = 0.85  # “自然さ”を出しつつ暴れすぎない

def get_settings() -> Settings:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is missing. Set it in .env or environment variables.")
    return Settings(openai_api_key=key)
