from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UsageSummary:
    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class GenerationResult:
    text: str
    model: str
    usage: UsageSummary | None = None
    estimated_cost_usd: str | None = None
