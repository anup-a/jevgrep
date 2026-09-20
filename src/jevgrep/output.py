"""Rendering verdicts in the shapes grep users expect."""

from __future__ import annotations

import json
from dataclasses import dataclass

from .colors import DIM, LINE_NUMBER, ORIGIN, SEPARATOR, confidence_color, paint
from .matcher import Verdict


@dataclass(frozen=True)
class OutputOptions:
    line_numbers: bool = False
    explain: bool = False
    jsonl: bool = False
    with_origin: bool = False
    color: bool = False


def _explain_prefix(verdict: Verdict, color: bool) -> str:
    probability = f"{verdict.probability:.2f}"
    confidence = "-" if verdict.confidence is None else f"{verdict.confidence:.2f}"

    body = (
        f"{paint('p=', DIM, color)}{paint(probability, confidence_color(verdict.probability), color)}"
        f" {paint('c=', DIM, color)}{paint(confidence, confidence_color(verdict.confidence), color)}"
    )
    return f"{paint('[', DIM, color)}{body}{paint(']', DIM, color)} "


def _as_json(verdict: Verdict) -> str:
    """Always uncoloured: this stream is parsed by other tools, not read by a human."""
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

    color = options.color
    record = verdict.record

    # A whole-file record's "text" is the entire file, so identify it by path instead.
    if record.is_whole_file:
        body = paint(record.origin, ORIGIN, color)
    else:
        separator = paint(":", SEPARATOR, color)
        prefix = f"{paint(record.origin, ORIGIN, color)}{separator}" if options.with_origin else ""
        number = (
            f"{paint(str(record.index), LINE_NUMBER, color)}{separator}"
            if options.line_numbers
            else ""
        )
        body = f"{prefix}{number}{record.text}"

    return f"{_explain_prefix(verdict, color)}{body}" if options.explain else body
