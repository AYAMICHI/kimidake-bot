from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

from .config import get_settings
from .logic.web_fortune import WebFortuneGenerator, WebFortuneInput
from .rate_limit import InMemoryRateLimiter
from .safety import CRISIS_MESSAGE, is_crisis_concern
from .services.mock_ai_client import MockOpenAITextClient
from .services.openai_client import OpenAITextClient


logger = logging.getLogger("kimidake.web")
PACKAGE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
rate_limiter = InMemoryRateLimiter(max_requests=3, window_seconds=60)

app = FastAPI(title="君だけの占い", version="0.1.0")
app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")


class FortuneRequest(BaseModel):
    nickname: str | None = Field(default=None, max_length=30)
    category: Literal["love", "reconciliation", "compatibility", "work", "today"]
    concern: str = Field(min_length=1, max_length=10_000)

    @field_validator("nickname")
    @classmethod
    def clean_nickname(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("concern")
    @classmethod
    def clean_concern(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("悩みを入力してください")
        return cleaned


class FortuneResponse(BaseModel):
    result: str = ""
    error: str | None = None


@lru_cache(maxsize=1)
def get_generator() -> tuple[WebFortuneGenerator, object]:
    settings = get_settings()
    if settings.use_mock_ai:
        client = MockOpenAITextClient()
    else:
        client = OpenAITextClient(
            api_key=settings.openai_api_key,
            timeout=settings.request_timeout_seconds,
        )
    generator = WebFortuneGenerator(PACKAGE_DIR / "prompts", client)
    return generator, settings


def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _request: Request, _exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"result": "", "error": "入力内容を確認してください。"},
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html")


@app.post("/api/fortune", response_model=FortuneResponse)
async def create_fortune(payload: FortuneRequest, request: Request):
    try:
        generator, settings = get_generator()
    except Exception as exc:
        logger.warning("fortune_configuration_failed type=%s", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={
                "result": "",
                "error": "現在、鑑定を利用できません。時間をおいてもう一度お試しください。",
            },
        )

    if len(payload.concern) > settings.max_input_chars_free:
        return JSONResponse(
            status_code=400,
            content={
                "result": "",
                "error": f"悩みは{settings.max_input_chars_free}文字以内で入力してください。",
            },
        )

    if is_crisis_concern(payload.concern):
        logger.warning("fortune_crisis_redirected")
        return FortuneResponse(result=CRISIS_MESSAGE)

    if not rate_limiter.allow(client_key(request)):
        return JSONResponse(
            status_code=429,
            content={
                "result": "",
                "error": "短時間に多くのリクエストがありました。1分ほど待ってからお試しください。",
            },
        )

    started = perf_counter()
    try:
        fortune_input = WebFortuneInput(
            nickname=payload.nickname,
            category=payload.category,
            concern=payload.concern,
        )
        result = await asyncio.wait_for(
            run_in_threadpool(generator.generate, fortune_input, settings=settings),
            timeout=settings.request_timeout_seconds + 2,
        )
    except asyncio.TimeoutError:
        logger.warning("fortune_failed reason=timeout")
        return JSONResponse(
            status_code=504,
            content={
                "result": "",
                "error": "鑑定に時間がかかっています。少し待ってからもう一度お試しください。",
            },
        )
    except Exception as exc:
        logger.warning("fortune_failed type=%s", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={
                "result": "",
                "error": "現在、鑑定を利用できません。時間をおいてもう一度お試しください。",
            },
        )

    elapsed_ms = int((perf_counter() - started) * 1000)
    estimated_tokens = max(1, len(result) // 4)
    logger.info(
        "fortune_succeeded model=%s elapsed_ms=%d estimated_output_tokens=%d",
        "mock" if settings.use_mock_ai else settings.model_free,
        elapsed_ms,
        estimated_tokens,
    )
    return FortuneResponse(result=result)


LEGAL_PAGES = {
    "terms": {
        "title": "利用規約",
        "body": "正式公開までに、利用条件、禁止事項、免責、サービス変更・停止について記載します。",
    },
    "privacy": {
        "title": "プライバシーポリシー",
        "body": "正式公開までに、入力情報の利用目的、OpenAI APIへの送信、保存期間、削除と問い合わせ方法について記載します。",
    },
    "tokusho": {
        "title": "特定商取引法に基づく表記",
        "body": "有料提供の開始前に、販売事業者、連絡先、価格、支払方法、提供時期、キャンセル・返金条件を記載します。",
    },
    "contact": {
        "title": "お問い合わせ",
        "body": "正式公開までに、運営者への問い合わせ方法を記載します。",
    },
    "premium": {
        "title": "プレミアム鑑定",
        "body": "プレミアム鑑定 500円は準備中です。決済はまだ発生しません。",
    },
}


def render_legal_page(request: Request, page: str) -> HTMLResponse:
    content = LEGAL_PAGES[page]
    return templates.TemplateResponse(
        request=request,
        name="legal.html",
        context={"title": content["title"], "body": content["body"]},
    )


@app.get("/terms", response_class=HTMLResponse)
async def terms(request: Request) -> HTMLResponse:
    return render_legal_page(request, "terms")


@app.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request) -> HTMLResponse:
    return render_legal_page(request, "privacy")


@app.get("/tokusho", response_class=HTMLResponse)
async def tokusho(request: Request) -> HTMLResponse:
    return render_legal_page(request, "tokusho")


@app.get("/contact", response_class=HTMLResponse)
async def contact(request: Request) -> HTMLResponse:
    return render_legal_page(request, "contact")


@app.get("/premium", response_class=HTMLResponse)
async def premium(request: Request) -> HTMLResponse:
    return render_legal_page(request, "premium")
