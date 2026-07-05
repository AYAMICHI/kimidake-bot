from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import logging

from .numerology import build_numerology
from ..utils.validators import (
    validate_birthday, validate_concern, validate_gender, validate_nickname
)

logger = logging.getLogger("kimidake")

WORLDVIEW_BANNED = [
    "宇宙", "波動", "引き寄せ", "高次元", "ソウルメイト"
]

HARD_BANNED = [
    "必ず儲かる", "絶対治る"
]

WORLDVIEW_FALLBACK_TEXT = (
    "大きな流れや特別な力を考えなくていい。\n"
    "いま見てほしいのは、目の前の現実だけ。\n\n"
    "今日できたことを一つ思い出して。\n"
    "それが、次に進むための十分な材料になる。"
)

HARD_FALLBACK_TEXT = (
    "いまの君は、ちょっと疲れてる。\n"
    "頑張りたい気持ちはあるのに、心が先にブレーキを踏んでる。\n\n"
    "今日やることは一つだけ。\n"
    "「5分だけ」手を動かして、止まってる感覚を壊す。\n"
    "小さく動いた瞬間から、流れは戻る。"
)


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
        return (
        "以下はLINE占いBot「君だけ」に届いた相談です。\n"
        "あなたはこの人の話し相手として、最初の返信を作ってください。\n\n"
        "【相談者】\n"
        f"ニックネーム：{fi.nickname}\n"
        f"性別：{fi.gender}\n"
        f"生年月日：{fi.birthday}\n\n"
        "【いまの悩み】\n"
        f"{fi.concern}\n\n"
        "【出力ルール】\n"
        "- 5つの段落に分ける（必ず改行）\n"
        "- 構成は以下の順で固定\n"
        "  ①状態の共感\n"
        "  ②自己否定の解除\n"
        "  ③意味づけの再定義\n"
        "  ④心の着地点\n"
        "  ⑤会話継続フック（短い質問 or 選択肢）\n"
        "- 行動指示はしない\n"
        "- 未来予測をしない\n"
        "- 説明口調にしない\n"
        "- スピ用語は禁止\n"
    )


    def _basic_safety_check(self, text: str) -> tuple[str, str]:
        # 危険断定 -> メンタル寄りの固定文
        if any(w in text for w in HARD_BANNED):
            return HARD_FALLBACK_TEXT, "hard"
        
        # 世界観ずれ ->トーン調整用の軽い文章
        if any(w in text for w in WORLDVIEW_BANNED):
            return WORLDVIEW_FALLBACK_TEXT, "worldview"
        
        return text, "none"

    def generate(self, raw: FortuneInput, *, settings, premium: bool = False) -> str:
        model = settings.model_premium if premium else settings.model_default
        
        fi = FortuneInput(
            nickname=validate_nickname(raw.nickname),
            birthday=validate_birthday(raw.birthday),
            gender=validate_gender(raw.gender),
            concern=validate_concern(raw.concern),
        )

        user_prompt = self._render_user_prompt(fi)
        
        logger.info("[fortune] start model=%s premium=%s", model, premium)
        
        out = self.llm_client.generate_fortune(
            model=model,
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            max_output_tokens=settings.max_output_tokens,
            temperature=settings.temperature,
        )
        out ,fallback = self._basic_safety_check(out)
        
        # ▼ ここで分割して数える（LINE想定）
        blocks = [b for b in out.split("\n\n") if b.strip()]
        logger.info("[fortune] blocks=%d fallback=%s", len(blocks), fallback)

        # 任意：各ブロックの長さを見る（最初だけ）
        for i, b in enumerate(blocks, 1):
            logger.info("[fortune] block_%d chars=%d", i, len(b))
        
        last = blocks[-1] if blocks else ""
        is_question = "？" in last or "?" in last
        logger.info("[fortune] hook_question=%s", is_question)


        # 最終出力のメタデータだけを記録し、鑑定本文は保存しない
        logger.info("[fortune] done model=%s premium=%s fallback=%s chars=%d", model, premium, fallback, len(out))
        
        return out
