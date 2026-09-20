"""jevsort: order records by how strongly a graded question holds."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass

from .client import ClientError
from .colors import WHEN_CHOICES, confidence_color, paint, should_color
from .concurrency import map_ordered
from .config import Config, ConfigError
from .records import Record, RecordError
from .runtime import (
    DEFAULT_JOBS,
    EXIT_EMPTY,
    EXIT_ERROR,
    EXIT_OK,
    fail,
    open_client,
    read_config,
    source_lines,
)
from .scoring import QUESTION_NAME, build_score_question


@dataclass(frozen=True)
class Ranked:
    record: Record
    score: float
    confidence: float | None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jevsort",
        description="Order records by how strongly a question holds, highest first.",
        epilog="Exit codes: 0 ranked something, 1 nothing to rank, 2 error.",
    )
    parser.add_argument("question", help="the graded question, e.g. 'how urgent is this?'")
    parser.add_argument("files", nargs="*", help="files to read; omit to read stdin")
    parser.add_argument("-r", "--reverse", action="store_true", help="lowest first")
    parser.add_argument("--top", type=int, help="keep only the N highest")
    parser.add_argument("--scale", type=int, default=5, help="points on the scale (default 5)")
    parser.add_argument("-j", "--jobs", type=int, default=DEFAULT_JOBS, help="requests in flight")
    parser.add_argument("--json", action="store_true", help="parse each input line as JSON")
    parser.add_argument("--explain", action="store_true", help="prefix the score")
    parser.add_argument("--jsonl", action="store_true", help="emit one JSON object per line")
    parser.add_argument("--color", choices=WHEN_CHOICES, default="auto", help="colourise output")
    parser.add_argument("--stats", action="store_true", help="report totals on stderr")
    return parser


def format_ranked(ranked: Ranked, explain: bool, jsonl: bool, color: bool) -> str:
    if jsonl:
        return json.dumps(
            {
                "origin": ranked.record.origin,
                "line": ranked.record.index,
                "text": ranked.record.text,
                "score": ranked.score,
                "confidence": ranked.confidence,
            }
        )
    if not explain:
        return ranked.record.text

    confidence = "-" if ranked.confidence is None else f"{ranked.confidence:.2f}"
    score = paint(f"{ranked.score:.2f}", confidence_color(ranked.confidence), color)
    return f"[{score} c={confidence}] {ranked.record.text}"


async def _run(args: argparse.Namespace, config: Config) -> int:
    question = build_score_question(args.question, steps=args.scale)
    started = time.monotonic()
    ranked: list[Ranked] = []
    failed = 0

    async with open_client(config) as client:

        async def score(record: Record):
            try:
                value, confidence = await client.evaluate_score(record, question, QUESTION_NAME)
            except ClientError as exc:
                return record, None, str(exc)
            return record, Ranked(record, value, confidence), None

        async for record, result, error in map_ordered(
            source_lines(args.files, parse_json=args.json), score, limit=args.jobs
        ):
            if error is not None:
                failed += 1
                print(f"jevsort: {record.origin}: {error}", file=sys.stderr)
                continue
            assert result is not None
            ranked.append(result)

        spent = client.spent

    # Python's sort is stable, so equal scores keep their input order.
    ranked.sort(key=lambda r: r.score, reverse=not args.reverse)
    if args.top is not None:
        ranked = ranked[: max(args.top, 0)]

    color = should_color(args.color, sys.stdout.isatty(), os.environ)
    for item in ranked:
        print(format_ranked(item, args.explain, args.jsonl, color))

    if args.stats:
        print(
            f"jevsort: {len(ranked) + failed} records, {failed} failed in "
            f"{time.monotonic() - started:.1f}s, market cost ${spent:.6f}",
            file=sys.stderr,
        )

    if failed:
        return EXIT_ERROR
    return EXIT_OK if ranked else EXIT_EMPTY


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.jobs < 1:
            raise ValueError(f"--jobs must be at least 1, got {args.jobs}")
        return asyncio.run(_run(args, read_config()))
    except (ConfigError, RecordError, ValueError) as exc:
        return fail(str(exc))
    except KeyboardInterrupt:
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
