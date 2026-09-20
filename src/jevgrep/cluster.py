"""Incremental semantic grouping.

Each record is shown the groups found so far and asked which one it belongs to, or
whether it is something new. That is one request per record rather than the pairwise
comparison a similarity threshold would need, and it plays to what Jev is good at:
picking from typed options it cannot invent alternatives to.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .records import Record

QUESTION_NAME = "group"
NEW_GROUP = "none"

# Representatives are quoted back inside the question, so keep them short.
REPRESENTATIVE_LIMIT = 240


@dataclass(frozen=True)
class Group:
    key: str
    representative: Record
    members: tuple[Record, ...]

    @property
    def size(self) -> int:
        return len(self.members)


def visible(groups: tuple[Group, ...], max_groups: int) -> tuple[Group, ...]:
    """The groups to offer as options, most recent first past the cap.

    A choice question cannot carry unbounded options, so beyond the cap only the most
    recently created groups compete. A record matching an older, evicted group therefore
    starts a duplicate one: the tradeoff is visible in the output rather than silent.
    """
    if max_groups < 1:
        raise ValueError(f"max_groups must be at least 1, got {max_groups}")
    return groups[-max_groups:]


def _shorten(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= REPRESENTATIVE_LIMIT:
        return collapsed
    return collapsed[: REPRESENTATIVE_LIMIT - 1] + "…"


def build_group_question(groups: tuple[Group, ...], aspect: str | None) -> dict[str, Any]:
    """Ask which existing group the candidate belongs to, if any."""
    if aspect and aspect.strip():
        sameness = f"say the same thing about {aspect.strip()}"
    else:
        sameness = "say essentially the same thing"

    criteria = {group.key: _shorten(group.representative.text) for group in groups}
    criteria[NEW_GROUP] = "None of these; the candidate is genuinely different"

    return {
        "type": "choice",
        "instructions": (
            f"Which of these existing groups does the candidate {sameness} as? "
            f"Answer {NEW_GROUP} unless it clearly belongs with one of them. "
            "Wording may differ; judge the meaning."
        ),
        "criteria": criteria,
    }


def assign(
    groups: tuple[Group, ...],
    record: Record,
    choice: str,
    confidence: float | None,
    min_confidence: float,
) -> tuple[Group, ...]:
    """Place the record, returning a new tuple of groups.

    A merge below the confidence floor becomes a new group instead. Merging is the
    destructive direction: a wrong merge hides a record from the output entirely, while
    a wrong split only costs a duplicate line that a human can still see.
    """
    unsure = min_confidence > 0.0 and (confidence is None or confidence < min_confidence)

    if choice == NEW_GROUP or unsure:
        return (*groups, Group(f"g{len(groups)}", record, (record,)))

    for index, group in enumerate(groups):
        if group.key == choice:
            merged = Group(group.key, group.representative, (*group.members, record))
            return (*groups[:index], merged, *groups[index + 1 :])

    raise ValueError(f"answer named an unknown group: {choice!r}")
