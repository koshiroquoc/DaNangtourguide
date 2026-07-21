"""Explicit migration helpers for the original synthetic CSV baseline."""

from __future__ import annotations

import re
from typing import Any


def parse_vnd_price(value: Any) -> tuple[int | None, int | None]:
    """Parse simple VND values/ranges such as ``35k`` or ``100k-200k``."""
    if value is None:
        return None, None
    text = str(value).casefold().replace(",", ".")
    amounts: list[int] = []
    for number, suffix in re.findall(r"(\d+(?:\.\d+)?)\s*([km]?)", text):
        amount = float(number)
        if suffix == "k":
            amount *= 1_000
        elif suffix == "m":
            amount *= 1_000_000
        candidate = int(round(amount))
        if candidate >= 1_000:
            amounts.append(candidate)
    if not amounts:
        return None, None
    return min(amounts), max(amounts)
