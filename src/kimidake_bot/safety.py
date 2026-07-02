from __future__ import annotations


CRISIS_KEYWORDS = (
    "死にたい",
    "消えたい",
    "自殺",
    "命を絶",
    "生きていたくない",
    "殺したい",
    "殺してやる",
)

CRISIS_MESSAGE = (
    "今は占いの結果をお返しするより、あなたの安全を最優先にしたい状況です。\n\n"
    "今すぐ自分や誰かを傷つける可能性がある場合は、一人にならず、"
    "安全な場所へ移動して、身近な人や地域の緊急窓口へ連絡してください。"
    "差し迫った危険がある場合は119または110へ連絡してください。\n\n"
    "このサービスは緊急相談には対応できません。医療機関や公的な相談窓口など、"
    "直接支援できる専門機関へ相談してください。"
)


def is_crisis_concern(text: str) -> bool:
    normalized = "".join(text.lower().split())
    return any(keyword in normalized for keyword in CRISIS_KEYWORDS)
