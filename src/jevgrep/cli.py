"""Command line entry point: argument parsing, orchestration, exit codes."""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from collections.abc import Iterator, Sequence

import httpx

from .client import ClientError, JevClient, build_proxy, build_verify
from .concurrency import map_ordered
from .config import Config, ConfigError, environment_with_dotenv, load_config
from .matcher import QUESTION_NAME, MatchOptions, Verdict, build_question, decide
from .output import OutputOptions, format_verdict
from .records import Record, RecordError, iter_file_lines, iter_files, iter_lines

EXIT_MATCH = 0
EXIT_NO_MATCH = 1
EXIT_ERROR = 2

DEFAULT_JOBS = 8


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jevgrep",
        description="grep, but the pattern is a question in English.",
        epilog="Exit codes: 0 matched, 1 no match, 2 error.",
    )
    parser.add_argument("predicate", help="the question to ask of every record")
    parser.add_argument("files", nargs="*", help="files to read; omit to read stdin")

    parser.add_argument("-v", "--invert-match", action="store_true", help="select non-matches")
    parser.add_argument("-c", "--count", action="store_true", help="print only the match count")
    parser.add_argument(
        "-l", "--files-with-matches", action="store_true", help="print matching origins once"
    )
    parser.add_argument("-n", "--line-number", action="store_true", help="prefix the line number")
    parser.add_argument("-q", "--quiet", action="store_true", help="no output, exit code only")

    parser.add_argument(
        "-t", "--threshold", type=float, default=0.5, help="probability to match (default 0.5)"
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.0,
        help="records Jev is less sure than this about never match",
    )
    parser.add_argument(
        "-j", "--jobs", type=int, default=DEFAULT_JOBS, help="requests in flight (default 8)"
    )

    parser.add_argument("--json", action="store_true", help="parse each input line as JSON")
    parser.add_argument("--whole", action="store_true", help="one record per file, not per line")
    parser.add_argument("--explain", action="store_true", help="prefix [p=… c=…]")
    parser.add_argument("--jsonl", action="store_true", help="emit one JSON verdict per line")
    parser.add_argument("--stats", action="store_true", help="report totals on stderr")
    return parser


def validate(args: argparse.Namespace) -> None:
    """Reject argument combinations that cannot mean anything, before spending money."""
    if not 0.0 <= args.threshold <= 1.0:
        raise ValueError(f"--threshold must be between 0 and 1, got {args.threshold}")
    if not 0.0 <= args.min_confidence <= 1.0:
        raise ValueError(f"--min-confidence must be between 0 and 1, got {args.min_confidence}")
    if args.jobs < 1:
        raise ValueError(f"--jobs must be at least 1, got {args.jobs}")
    if args.whole and args.json:
        raise ValueError("--whole and --json cannot be combined: a file is not a JSON line")


def source_records(args: argparse.Namespace) -> Iterator[Record]:
    if args.whole:
        if not args.files:
            raise RecordError("--whole needs file arguments; it cannot read stdin")
        return iter_files(args.files)
    if args.files:
        return iter_file_lines(args.files, parse_json=args.json)
    return iter_lines(sys.stdin, parse_json=args.json)


def _emit(verdict: Verdict, args: argparse.Namespace, seen: set[str]) -> None:
    if args.quiet or args.count:
        return
    if args.files_with_matches:
        if verdict.record.origin in seen:
            return
        seen.add(verdict.record.origin)
        print(verdict.record.origin)
        return

    options = OutputOptions(
        line_numbers=args.line_number,
        explain=args.explain,
        jsonl=args.jsonl,
        with_origin=len(args.files) > 1 and not args.whole,
    )
    print(format_verdict(verdict, options))


async def _run(args: argparse.Namespace, config: Config) -> int:
    question = build_question(args.predicate)
    match_options = MatchOptions(
        threshold=args.threshold, min_confidence=args.min_confidence, invert=args.invert_match
    )

    total = matched = uncertain = failed = 0
    seen: set[str] = set()
    started = time.monotonic()

    async with httpx.AsyncClient(
        verify=build_verify(), proxy=build_proxy(), trust_env=False
    ) as http:
        client = JevClient(config, http)

        async def evaluate(record: Record) -> tuple[Record, Verdict | None, str | None]:
            try:
                probability, confidence = await client.evaluate(record, question, QUESTION_NAME)
            except ClientError as exc:
                return record, None, str(exc)
            return record, decide(record, probability, confidence, match_options), None

        async for record, verdict, error in map_ordered(
            source_records(args), evaluate, limit=args.jobs
        ):
            total += 1
            if error is not None:
                failed += 1
                print(f"jevgrep: {record.origin}: {error}", file=sys.stderr)
                continue
            assert verdict is not None
            if verdict.uncertain:
                uncertain += 1
            if verdict.matched:
                matched += 1
                _emit(verdict, args, seen)
                if args.quiet:
                    break  # grep -q stops at the first match; here it also stops spending

    if args.count:
        print(matched)
    if uncertain:
        print(
            f"jevgrep: {uncertain} record(s) were too uncertain to classify "
            f"(below --min-confidence {args.min_confidence})",
            file=sys.stderr,
        )
    if args.stats:
        elapsed = time.monotonic() - started
        print(
            f"jevgrep: {total} records, {matched} matched, {uncertain} uncertain, "
            f"{failed} failed in {elapsed:.1f}s, market cost ${client.spent:.6f}",
            file=sys.stderr,
        )

    if failed:
        return EXIT_ERROR
    return EXIT_MATCH if matched else EXIT_NO_MATCH


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        validate(args)
        config = load_config(environment_with_dotenv())
        return asyncio.run(_run(args, config))
    except (ConfigError, RecordError, ValueError) as exc:
        print(f"jevgrep: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except KeyboardInterrupt:
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
