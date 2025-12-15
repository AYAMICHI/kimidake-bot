from __future__ import annotations
from openai import OpenAI

class OpenAITextClient:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def generate_fortune(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int,
        temperature: float,
    ) -> str:
        # Responses API（公式推奨） :contentReference[oaicite:2]{index=2}
        resp = self.client.responses.create(
            model=model,
            instructions=system_prompt,
            input=user_prompt,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )
        text = (resp.output_text or "").strip()
        return text
