from __future__ import annotations

import logging
from dataclasses import dataclass

from openai import OpenAI


usage_logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class ModelPricing:
    input_per_million_usd: float
    cached_input_per_million_usd: float
    output_per_million_usd: float


# 2026-07-05時点のOpenAI標準テキスト料金。単価変更時は公式料金表と合わせて更新する。
MODEL_PRICING = {
    "gpt-5.4-mini": ModelPricing(0.75, 0.075, 4.50),
    "gpt-5.5": ModelPricing(5.00, 0.50, 30.00),
}


def _pricing_for_model(model: str) -> ModelPricing | None:
    for base_model, pricing in MODEL_PRICING.items():
        if model == base_model or model.startswith(f"{base_model}-20"):
            return pricing
    return None


def _estimated_cost_usd(model: str, usage) -> float | None:
    pricing = _pricing_for_model(model)
    if pricing is None:
        return None

    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    input_details = getattr(usage, "input_tokens_details", None)
    cached_tokens = int(getattr(input_details, "cached_tokens", 0) or 0)
    cached_tokens = min(max(cached_tokens, 0), input_tokens)
    uncached_tokens = input_tokens - cached_tokens

    return (
        uncached_tokens * pricing.input_per_million_usd
        + cached_tokens * pricing.cached_input_per_million_usd
        + output_tokens * pricing.output_per_million_usd
    ) / 1_000_000


def _log_usage(model: str, usage) -> None:
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", 0) or 0)
    estimated_cost = _estimated_cost_usd(model, usage)
    estimated_cost_text = (
        f"{estimated_cost:.8f}" if estimated_cost is not None else "unknown"
    )
    usage_logger.info(
        "model=%s input_tokens=%d output_tokens=%d total_tokens=%d estimated_cost_usd=%s",
        model,
        input_tokens,
        output_tokens,
        total_tokens,
        estimated_cost_text,
    )


class OpenAITextClient:
    def __init__(self, api_key: str, *, timeout: float = 25.0):
        self.client = OpenAI(api_key=api_key, timeout=timeout, max_retries=1)

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
        if resp.usage is not None:
            response_model = getattr(resp, "model", None) or model
            _log_usage(response_model, resp.usage)
        text = (resp.output_text or "").strip()
        return text
