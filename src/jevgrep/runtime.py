"""Plumbing shared by every tool in the suite: exit codes, sourcing records, the client."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import asynccontextmanager

import httpx

from .client import JevClient, build_proxy, build_verify
from .config import Config, environment_with_dotenv, load_config
from .records import Record, RecordError, iter_file_lines, iter_lines

EXIT_OK = 0
EXIT_EMPTY = 1
EXIT_ERROR = 2

DEFAULT_JOBS = 8


def source_lines(files: list[str], parse_json: bool = False) -> Iterator[Record]:
    """One record per line, from the named files or from stdin."""
    if files:
        return iter_file_lines(files, parse_json=parse_json)
    return iter_lines(sys.stdin, parse_json=parse_json)


def read_config() -> Config:
    return load_config(environment_with_dotenv())


@asynccontextmanager
async def open_client(config: Config):
    """A JevClient with the suite's TLS and proxy handling applied."""
    async with httpx.AsyncClient(
        verify=build_verify(), proxy=build_proxy(), trust_env=False
    ) as http:
        yield JevClient(config, http)


def fail(message: str) -> int:
    print(f"{_program()}: {message}", file=sys.stderr)
    return EXIT_ERROR


def warn(message: str) -> None:
    print(f"{_program()}: {message}", file=sys.stderr)


def _program() -> str:
    import os

    return os.path.basename(sys.argv[0]) or "jev"


__all__ = [
    "DEFAULT_JOBS",
    "EXIT_EMPTY",
    "EXIT_ERROR",
    "EXIT_OK",
    "RecordError",
    "fail",
    "open_client",
    "read_config",
    "source_lines",
    "warn",
]
