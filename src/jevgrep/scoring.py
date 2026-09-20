"""Graded questions: rank records on a scale instead of filtering them yes/no."""

from __future__ import annotations

from typing import Any

QUESTION_NAME = "rank"

DEFAULT_STEPS = 5
MIN_STEPS = 2
MAX_STEPS = 10


def build_score_question(question: str, steps: int = DEFAULT_STEPS) -> dict[str, Any]:
    """Build a Jev `score` question.

    `criteria` must be an ARRAY here, unlike a choice question's object, and its length
    is what defines the bucket range: five entries score 0..4. The gateway rejects an
    object with a Zod union error, so this is not interchangeable with build_question.
    """
    cleaned = question.strip()
    if not cleaned:
        raise ValueError("the question is empty")
    if not MIN_STEPS <= steps <= MAX_STEPS:
        raise ValueError(f"--scale must be between {MIN_STEPS} and {MAX_STEPS}, got {steps}")

    top = steps - 1
    criteria = [f"{i} = middle of the scale" for i in range(steps)]
    criteria[0] = "0 = not at all"
    criteria[top] = f"{top} = completely, the strongest possible case"

    return {
        "type": "score",
        "instructions": (
            f"Rate the record on this question: {cleaned}\n"
            f"Answer on a {steps}-point scale from 0 to {top}. Judge only from the record "
            "itself, and use the whole scale rather than clustering in the middle."
        ),
        "criteria": criteria,
    }
