import re

def clean_text(s: str) -> str:
    return (s or "").strip()

def validate_nickname(nickname: str) -> str:
    nickname = clean_text(nickname)
    if not nickname:
        return "あなた"
    # LINE表示名が長いケースの保険
    return nickname[:20]

def validate_gender(gender: str) -> str:
    g = clean_text(gender).lower()
    # 口調調整用なので厳密にしない
    if g in {"male", "man", "m", "男"}:
        return "male"
    if g in {"female", "woman", "f", "女"}:
        return "female"
    return "neutral"

def validate_birthday(birthday: str) -> str:
    b = clean_text(birthday)
    if not b:
        raise ValueError("birthday is required")
    # 2000/01/02, 2000-01-02, 20000102 などを許容（厳密パースは numerology 側）
    if not re.search(r"\d", b):
        raise ValueError("birthday must contain digits")
    return b

def validate_concern(concern: str) -> str:
    c = clean_text(concern)
    # MVP：未入力なら「いまの状態」で生成する
    return c[:80]  # 長文は切る
