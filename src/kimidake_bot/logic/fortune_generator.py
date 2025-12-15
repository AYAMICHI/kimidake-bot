from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

from kimidake_bot.logic.numerology import build_numerology
from kimidake_bot.utils.validators import (
    validate_birthday, validate_concern, validate_gender, validate_nickname
)

BANNED_HINTS = [
    "宇宙", "波動", "引き寄せ", "高次元", "ソウルメイト",
    "必ず儲かる", "絶対治る",
]

@dataclass(frozen=True)
class FortuneInput:
    nickname: str
    birthday: str
    gender: str
    concern: str

class FortuneGenerator:
    def __init__(self, prompts_dir: Path, llm_client):
        self.prompts_dir = prompts_dir
        self.llm_client = llm_client
        self.system_prompt = (prompts_dir / "system.txt").read_text(encoding="utf-8")
        self.user_template = (prompts_dir / "user_template.txt").read_text(encoding="utf-8")

    def _render_user_prompt(self, fi: FortuneInput) -> str:
        n = build_numerology(fi.birthday)
        return self.user_template.format(
            nickname=fi.nickname,
            birthday=fi.birthday,
            gender=fi.gender,
            concern=fi.concern or "（未入力）",
            life_path=n.life_path,
            birth_month=n.birth_month,
        )

    def _basic_safety_check(self, text: str) -> str:
        # MVP: 禁止ワードが濃ければ“やさしく差し替え”
        for w in BANNED_HINTS:
            if w in text:
                return (
                    "いまの君は、ちょっと疲れてる。\n"
                    "頑張りたい気持ちはあるのに、心が先にブレーキを踏んでる。\n"
                    "今日やることは一つだけ。\n"
                    "「5分だけ」手を動かして、止まってる感覚を壊す。\n"
                    "小さく動いた瞬間から、流れは戻る。"
                )
        return text

    def generate(self, raw: FortuneInput, *, settings, premium: bool = False) -> str:
        model = settings.model_premium if premium else settings.model_default
        fi = FortuneInput(
            nickname=validate_nickname(raw.nickname),
            birthday=validate_birthday(raw.birthday),
            gender=validate_gender(raw.gender),
            concern=validate_concern(raw.concern),
        )

        user_prompt = self._render_user_prompt(fi)
        out = self.llm_client.generate_fortune(
            model=model,
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            max_output_tokens=settings.max_output_tokens,
            temperature=settings.temperature,
        )
        out = self._basic_safety_check(out)
        return out