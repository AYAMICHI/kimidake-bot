from __future__ import annotations
import re
from dataclasses import dataclass

MASTER = {11, 22, 33}

@dataclass(frozen=True)
class Numerology:
    life_path: int
    birth_month: int | None

def _reduce(n: int) -> int:
    while n not in MASTER and n > 9:
        n = sum(int(d) for d in str(n))
    return n

def life_path_number(birthday: str) -> int:
    digits = [int(ch) for ch in birthday if ch.isdigit()]
    if not digits:
        raise ValueError("birthday has no digits")
    return _reduce(sum(digits))

def birth_month(birthday: str) -> int | None:
    s = birthday.strip()
    m = re.search(r"(\d{1,4})[/-](\d{1,2})[/-](\d{1,2})", s)
    if m:
        mm = int(m.group(2))
        return mm if 1 <= mm <= 12 else None
    digits = re.sub(r"\D", "", s)
    if len(digits) >= 6:
        mm = int(digits[4:6])
        return mm if 1 <= mm <= 12 else None
    return None

def build_numerology(birthday: str) -> Numerology:
    return Numerology(
        life_path=life_path_number(birthday),
        birth_month=birth_month(birthday),
    )
