from __future__ import annotations

import random
import re
from typing import Any

KEYWORD_RE = re.compile(
    r"\b(def|class|return|if|else|for|while|try|except|import|from|function|const|let|var|SELECT|INSERT|UPDATE)\b",
    re.IGNORECASE,
)


def _score_fragment(content: str) -> float:
    text = content.strip()
    if not text:
        return 0.01

    score = 1.0

    length = len(text)
    if 20 <= length <= 180:
        score += 1.5
    elif length > 250:
        score *= 0.6

    if KEYWORD_RE.search(text):
        score += 1.0

    if any(ch.isalpha() for ch in text) and any(ch in "(){}[]" for ch in text):
        score += 0.8

    if text.startswith(("#", "//", "/*", "--")):
        score += 0.3

    return max(score, 0.05)


def select_fragments(
    candidates: list[dict[str, Any]],
    count: int,
    entropy: float,
    rng: random.Random,
) -> list[dict[str, Any]]:
    if not candidates:
        return []

    count = min(count, len(candidates))
    entropy = max(0.0, min(1.0, entropy))

    pool = list(candidates)
    selected: list[dict[str, Any]] = []

    for _ in range(count):
        weights = []
        for item in pool:
            quality = _score_fragment(item["content"])
            chaos = rng.uniform(0.2, 1.8)
            weights.append((1.0 - entropy) * quality + entropy * chaos)

        pick_index = rng.choices(range(len(pool)), weights=weights, k=1)[0]
        selected.append(pool.pop(pick_index))

    return selected
