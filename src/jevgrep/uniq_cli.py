"""jevuniq: collapse records that mean the same thing, however they are worded."""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from collections.abc import Sequence

from .client import ClientError, answer_confidence
from .cluster import QUESTION_NAME, Group, assign, build_group_question, visible
from .config import Config, ConfigError
from .records import RecordError
from .runtime import (
    EXIT_EMPTY,
    EXIT_ERROR,
    EXIT_OK,
    fail,
    open_client,
    read_config,
    source_lines,
)

DEFAULT_MAX_GROUPS = 24


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jevuniq",
        description="Collapse records that mean the same thing, regardless of wording.",
        epilog="Exit codes: 0 produced groups, 1 nothing to group, 2 error.",
    )
    parser.add_argument("files", nargs="*", help="files to read; omit to read stdin")
    parser.add_argument("--by", help="what sameness means here, e.g. 'the underlying bug'")
    parser.add_argument("-c", "--count", action="store_true", help="prefix each group's size")
    parser.add_argument(
        "-d", "--repeated", action="store_true", help="only groups with more than one member"
    )
    parser.add_argument(
        "-u", "--unique", action="store_true", help="only groups with exactly one member"
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.0,
        help="never merge on an answer Jev is less sure than this about",
    )
    parser.add_argument(
        "--max-groups",
        type=int,
        default=DEFAULT_MAX_GROUPS,
        help=f"groups offered as options at once (default {DEFAULT_MAX_GROUPS})",
    )
    parser.add_argument("--json", action="store_true", help="parse each input line as JSON")
    parser.add_argument("--stats", action="store_true", help="report totals on stderr")
    return parser


def select(groups: tuple[Group, ...], args: argparse.Namespace) -> tuple[Group, ...]:
    if args.repeated:
        return tuple(g for g in groups if g.size > 1)
    if args.unique:
        return tuple(g for g in groups if g.size == 1)
    return groups


async def _run(args: argparse.Namespace, config: Config) -> int:
    groups: tuple[Group, ...] = ()
    total = failed = 0
    started = time.monotonic()

    async with open_client(config) as client:
        # Grouping is inherently sequential: each decision depends on the groups that
        # exist so far, so there is nothing to parallelise here.
        for record in source_lines(args.files, parse_json=args.json):
            total += 1
            question = build_group_question(visible(groups, args.max_groups), args.by)
            state = {"candidate": record.text}
            try:
                payload = await client.ask(state, question, QUESTION_NAME)
            except ClientError as exc:
                failed += 1
                print(f"jevuniq: {record.origin}: {exc}", file=sys.stderr)
                continue

            answer = (payload.get("answers") or {}).get(QUESTION_NAME) or {}
            choice = answer.get("choice")
            if not isinstance(choice, str) or choice not in question["criteria"]:
                failed += 1
                print(f"jevuniq: {record.origin}: unusable answer {choice!r}", file=sys.stderr)
                continue

            groups = assign(
                groups,
                record,
                choice,
                answer_confidence(payload, QUESTION_NAME),
                args.min_confidence,
            )

        spent = client.spent

    shown = select(groups, args)
    for group in shown:
        if args.count:
            print(f"{group.size:>7} {group.representative.text}")
        else:
            print(group.representative.text)

    if args.stats:
        print(
            f"jevuniq: {total} records, {len(groups)} groups, {failed} failed in "
            f"{time.monotonic() - started:.1f}s, market cost ${spent:.6f}",
            file=sys.stderr,
        )

    if failed:
        return EXIT_ERROR
    return EXIT_OK if shown else EXIT_EMPTY


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.repeated and args.unique:
            raise ValueError("--repeated and --unique are opposites; pick one")
        if args.max_groups < 1:
            raise ValueError(f"--max-groups must be at least 1, got {args.max_groups}")
        if not 0.0 <= args.min_confidence <= 1.0:
            raise ValueError(f"--min-confidence must be between 0 and 1, got {args.min_confidence}")
        return asyncio.run(_run(args, read_config()))
    except (ConfigError, RecordError, ValueError) as exc:
        return fail(str(exc))
    except KeyboardInterrupt:
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
