"""Rendering verdicts in the shapes grep users expect."""

from __future__ import annotations

import json
from dataclasses import dataclass

from .matcher import Verdict


@dataclass(frozen=True)
class OutputOptions:
    line_numbers: bool = False
    explain: bool = False
    jsonl: bool = False
    with_origin: bool = False


def _explain_prefix(verdict: Verdict) -> str:
    confidence = "-" if verdict.confidence is None else f"{verdict.confidence:.2f}"
    return f"[p={verdict.probability:.2f} c={confidence}] "


def _as_json(verdict: Verdict) -> str:
    record = verdict.record
    return json.dumps(
        {
            "origin": record.origin,
            "line": None if record.is_whole_file else record.index,
            "text": record.text,
            "probability": verdict.probability,
            "confidence": verdict.confidence,
            "matched": verdict.matched,
            "uncertain": verdict.uncertain,
        }
    )


def format_verdict(verdict: Verdict, options: OutputOptions) -> str:
    """Render one verdict as a single output line."""
    if options.jsonl:
        return _as_json(verdict)

    record = verdict.record
    # A whole-file record's "text" is the entire file, so identify it by path instead.
    if record.is_whole_file:
        body = record.origin
    else:
        prefix = f"{record.origin}:" if options.with_origin else ""
        number = f"{record.index}:" if options.line_numbers else ""
        body = f"{prefix}{number}{record.text}"

    return f"{_explain_prefix(verdict)}{body}" if options.explain else body
