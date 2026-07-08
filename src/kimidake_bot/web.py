from __future__ import annotations

import asyncio
import logging
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from openai import BadRequestError
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool

from .analytics import (
    AnalyticsEvent,
    AnalyticsStore,
    analytics_enabled,
    analytics_storage,
    hash_user_agent,
)
from .config import get_settings, premium_preview_enabled
from .logic.premium_fortune import PremiumFortuneGenerator
from .logic.web_fortune import WebFortuneGenerator, WebFortuneInput
from .rate_limit import InMemoryRateLimiter
from .safety import CRISIS_MESSAGE, is_crisis_concern
from .services.mock_ai_client import MockOpenAITextClient
from .services.openai_error_diagnostics import log_openai_bad_request
from .services.openai_client import OpenAITextClient


logger = logging.getLogger("kimidake.web")
PACKAGE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
rate_limiter = InMemoryRateLimiter(max_requests=3, window_seconds=60)

app = FastAPI(title="君だけの占い", version="0.1.0")
app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")


class FortuneRequest(BaseModel):
    nickname: str | None = Field(default=None, max_length=30)
    birthday: date | None = None
    category: Literal["love", "reconciliation", "compatibility", "work", "today"]
    concern: str = Field(min_length=1, max_length=10_000)

    @field_validator("nickname")
    @classmethod
    def clean_nickname(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("birthday", mode="before")
    @classmethod
    def validate_birthday(cls, value):
        if value is None or value == "":
            return None
        if isinstance(value, date):
            birthday = value
        else:
            if not isinstance(value, str) or not re.fullmatch(r"\d{4}([-\/])\d{2}\1\d{2}", value):
                raise ValueError("生年月日はYYYY-MM-DDまたはYYYY/MM/DD形式で入力してください")
            try:
                birthday = date.fromisoformat(value.replace("/", "-"))
            except ValueError as exc:
                raise ValueError("存在する日付を入力してください") from exc

        today = date.today()
        if birthday > today:
            raise ValueError("未来の生年月日は入力できません")
        if birthday < oldest_allowed_birthday(today):
            raise ValueError("生年月日は過去120年以内で入力してください")
        return birthday

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


class PremiumFortuneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nickname: str | None = Field(default=None, max_length=30)
    birthdate: date | None = None
    category: Literal["love", "reconciliation", "compatibility", "work", "today"]
    concern: str = Field(min_length=1, max_length=10_000)
    free_result: str | None = Field(default=None, max_length=10_000)

    @field_validator("nickname")
    @classmethod
    def clean_nickname(cls, value: str | None) -> str | None:
        return FortuneRequest.clean_nickname(value)

    @field_validator("birthdate", mode="before")
    @classmethod
    def validate_birthdate(cls, value):
        return FortuneRequest.validate_birthday(value)

    @field_validator("concern")
    @classmethod
    def clean_concern(cls, value: str) -> str:
        return FortuneRequest.clean_concern(value)


class UsageResponse(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int


class PremiumFortuneResponse(BaseModel):
    result: str = ""
    error: str | None = None
    estimated_cost_usd: str | None = None
    usage: UsageResponse | None = None


class AnalyticsEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_name: Literal["result_view", "cta_click"]
    category: Literal["love", "reconciliation", "compatibility", "work", "today"]
    has_birthdate: bool
    session_id: str = Field(
        min_length=16,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class AnalyticsEventResponse(BaseModel):
    ok: bool


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


def get_premium_generator() -> tuple[PremiumFortuneGenerator, object]:
    free_generator, settings = get_generator()
    return PremiumFortuneGenerator(PACKAGE_DIR / "prompts", free_generator.llm_client), settings


@lru_cache(maxsize=1)
def get_analytics_store() -> AnalyticsStore | None:
    if not analytics_enabled():
        return None
    if analytics_storage() != "sqlite":
        raise RuntimeError("Only sqlite analytics storage is supported")
    return AnalyticsStore()


def save_analytics_event(payload: AnalyticsEventRequest, user_agent: str | None) -> None:
    store = get_analytics_store()
    if store is None:
        return
    store.record_event(
        AnalyticsEvent(
            event_name=payload.event_name,
            category=payload.category,
            has_birthdate=payload.has_birthdate,
            session_id=payload.session_id,
            user_agent_hash=hash_user_agent(user_agent),
        )
    )


def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def oldest_allowed_birthday(today: date) -> date:
    try:
        return today.replace(year=today.year - 120)
    except ValueError:
        return today.replace(year=today.year - 120, day=28)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    if any(
        "birthday" in error.get("loc", ()) or "birthdate" in error.get("loc", ())
        for error in exc.errors()
    ):
        message = "生年月日はYYYY-MM-DDまたはYYYY/MM/DD形式の実在する過去120年以内の日付で入力してください。"
    else:
        message = "入力内容を確認してください。"
    return JSONResponse(
        status_code=400,
        content={"result": "", "error": message},
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    today = date.today()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "birthday_min": oldest_allowed_birthday(today).isoformat(),
            "birthday_max": today.isoformat(),
            "premium_preview_enabled": premium_preview_enabled(),
        },
    )


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

    try:
        fortune_input = WebFortuneInput(
            nickname=payload.nickname,
            birthday=payload.birthday,
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

    return FortuneResponse(result=result)


@app.post("/api/premium-fortune", response_model=PremiumFortuneResponse)
async def create_premium_fortune(payload: PremiumFortuneRequest, request: Request):
    if not premium_preview_enabled():
        return JSONResponse(
            status_code=403,
            content={
                "result": "",
                "error": "プレミアム鑑定プレビューは無効です。",
                "estimated_cost_usd": None,
                "usage": None,
            },
        )

    try:
        generator, settings = get_premium_generator()
    except Exception as exc:
        logger.warning("premium_configuration_failed type=%s", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={
                "result": "",
                "error": "現在、プレミアム鑑定を利用できません。",
                "estimated_cost_usd": None,
                "usage": None,
            },
        )

    if not settings.enable_premium_preview:
        return JSONResponse(
            status_code=403,
            content={
                "result": "",
                "error": "プレミアム鑑定プレビューは無効です。",
                "estimated_cost_usd": None,
                "usage": None,
            },
        )
    if len(payload.concern) > settings.max_input_chars_premium:
        return JSONResponse(
            status_code=400,
            content={
                "result": "",
                "error": f"悩みは{settings.max_input_chars_premium}文字以内で入力してください。",
                "estimated_cost_usd": None,
                "usage": None,
            },
        )
    if is_crisis_concern(payload.concern):
        logger.warning("premium_fortune_crisis_redirected")
        return PremiumFortuneResponse(result=CRISIS_MESSAGE)
    if not rate_limiter.allow(client_key(request)):
        return JSONResponse(
            status_code=429,
            content={
                "result": "",
                "error": "短時間に多くのリクエストがありました。1分ほど待ってからお試しください。",
                "estimated_cost_usd": None,
                "usage": None,
            },
        )

    try:
        fortune_input = WebFortuneInput(
            nickname=payload.nickname,
            birthday=payload.birthdate,
            category=payload.category,
            concern=payload.concern,
        )
        generated = await asyncio.wait_for(
            run_in_threadpool(
                generator.generate,
                fortune_input,
                free_result=payload.free_result,
                settings=settings,
            ),
            timeout=settings.request_timeout_seconds + 5,
        )
    except asyncio.TimeoutError:
        logger.warning("premium_fortune_failed reason=timeout")
        return JSONResponse(
            status_code=504,
            content={
                "result": "",
                "error": "プレミアム鑑定に時間がかかっています。少し待ってからもう一度お試しください。",
                "estimated_cost_usd": None,
                "usage": None,
            },
        )
    except BadRequestError as exc:
        birthdate_iso = payload.birthdate.isoformat() if payload.birthdate else None
        birthdate_slash = birthdate_iso.replace("-", "/") if birthdate_iso else None
        log_openai_bad_request(
            exc,
            sensitive_values=(
                settings.openai_api_key,
                payload.concern,
                birthdate_iso,
                birthdate_slash,
                payload.free_result,
            ),
        )
        return JSONResponse(
            status_code=503,
            content={
                "result": "",
                "error": "OpenAI APIがプレミアム鑑定リクエストを受け付けませんでした。開発コンソールを確認してください。",
                "estimated_cost_usd": None,
                "usage": None,
            },
        )
    except Exception as exc:
        logger.warning("premium_fortune_failed type=%s", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={
                "result": "",
                "error": "現在、プレミアム鑑定を利用できません。時間をおいてもう一度お試しください。",
                "estimated_cost_usd": None,
                "usage": None,
            },
        )

    usage = None
    if generated.usage is not None:
        usage = UsageResponse(
            input_tokens=generated.usage.input_tokens,
            output_tokens=generated.usage.output_tokens,
            total_tokens=generated.usage.total_tokens,
        )
    return PremiumFortuneResponse(
        result=generated.result,
        estimated_cost_usd=generated.estimated_cost_usd,
        usage=usage,
    )


@app.post("/api/events", response_model=AnalyticsEventResponse)
async def record_analytics_event(
    payload: AnalyticsEventRequest, request: Request
) -> AnalyticsEventResponse:
    try:
        await run_in_threadpool(
            save_analytics_event,
            payload,
            request.headers.get("user-agent"),
        )
    except Exception as exc:
        logger.warning("analytics_event_failed type=%s", type(exc).__name__)
        return AnalyticsEventResponse(ok=False)
    return AnalyticsEventResponse(ok=True)


LEGAL_PAGES = {
    "terms": {
        "title": "利用規約",
        "body": "正式公開までに、利用条件、禁止事項、免責、サービス変更・停止について記載します。",
    },
    "privacy": {
        "title": "プライバシーポリシー",
        "body": "正式公開までに、入力情報の利用目的、OpenAI APIへの送信、匿名利用イベント、保存期間、削除と問い合わせ方法について記載します。",
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
