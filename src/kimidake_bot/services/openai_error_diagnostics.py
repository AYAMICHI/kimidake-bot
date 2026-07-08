from __future__ import annotations

import logging
import re
from collections.abc import Iterable

from openai import BadRequestError


diagnostics_logger = logging.getLogger("uvicorn.error")
_API_KEY_PATTERN = re.compile(r"\b(?:sk|sess)-[A-Za-z0-9_-]{8,}\b")


def _error_payload(error: BadRequestError) -> dict:
    body = error.body
    if not isinstance(body, dict):
        return {}
    nested = body.get("error")
    return nested if isinstance(nested, dict) else body


def _safe_text(value, *, sensitive_values: Iterable[str | None], limit: int) -> str:
    text = str(value or "unknown").replace("\r", " ").replace("\n", " ")
    for sensitive_value in sensitive_values:
        if sensitive_value:
            text = text.replace(str(sensitive_value), "[REDACTED]")
    text = _API_KEY_PATTERN.sub("[REDACTED_API_KEY]", text)
    return text[:limit]


def log_openai_bad_request(
    error: BadRequestError, *, sensitive_values: Iterable[str | None] = ()
) -> None:
    """開発用に、BadRequestの許可済み項目だけを安全に記録する。"""
    sensitive_values = tuple(sensitive_values)
    payload = _error_payload(error)
    error_code = payload.get("code") or getattr(error, "code", None)
    rejected_parameter = payload.get("param") or getattr(error, "param", None)
    error_message = payload.get("message") or getattr(error, "message", None)
    status_code = getattr(error, "status_code", None)

    diagnostics_logger.warning(
        "openai_bad_request status_code=%s error_code=%s rejected_parameter=%s error_message=%s",
        status_code if status_code is not None else "unknown",
        _safe_text(error_code, sensitive_values=sensitive_values, limit=160),
        _safe_text(rejected_parameter, sensitive_values=sensitive_values, limit=200),
        _safe_text(error_message, sensitive_values=sensitive_values, limit=1_000),
    )
