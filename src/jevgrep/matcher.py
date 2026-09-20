"""Turning a probability into a match decision."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .records import Record

QUESTION_NAME = "match"
YES = "yes"
NO = "no"

_YES_CRITERION = "The statement is true of the record."
_NO_CRITERION = "The statement is not true of the record, or the record says nothing about it."


@dataclass(frozen=True)
class MatchOptions:
    threshold: float = 0.5
    min_confidence: float = 0.0
    invert: bool = False


@dataclass(frozen=True)
class Verdict:
    record: Record
    probability: float
    confidence: float | None
    matched: bool
    uncertain: bool


def build_question(predicate: str) -> dict[str, Any]:
    """Build the Jev question that asks the user's predicate of one record.

    A two-way choice rather than type=boolean on purpose: the gateway returns a bare
    probability for boolean answers and no entry in providerMetadata.typesafe.confidence,
    which would silently make --min-confidence do nothing. A choice returns both.
    """
    cleaned = predicate.strip()
    if not cleaned:
        raise ValueError("the predicate is empty")

    return {
        "type": "choice",
        "instructions": (
            "Decide whether the following statement is true of the record in the state: "
            f"{cleaned}\n"
            "Judge only from the record itself. If the record does not contain enough "
            "information to tell, answer no."
        ),
        "criteria": {YES: _YES_CRITERION, NO: _NO_CRITERION},
    }


def decide(
    record: Record, probability: float, confidence: float | None, options: MatchOptions
) -> Verdict:
    """Combine probability, confidence and options into a single immutable Verdict."""
    if not 0.0 <= probability <= 1.0:
        raise ValueError(f"probability out of range: {probability}")

    # A confidence floor only bites if one was asked for; Jev omits confidence on booleans.
    uncertain = options.min_confidence > 0.0 and (
        confidence is None or confidence < options.min_confidence
    )

    if uncertain:
        matched = False  # never guess on the model's behalf, in either direction
    else:
        above = probability >= options.threshold
        matched = not above if options.invert else above

    return Verdict(
        record=record,
        probability=probability,
        confidence=confidence,
        matched=matched,
        uncertain=uncertain,
    )
