"""Turning input into records: one per line by default, or one per file under --whole."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any, TextIO

STDIN_ORIGIN = "(standard input)"

# Whole-file records have no meaningful line number; 0 marks them.
WHOLE_FILE_INDEX = 0


class RecordError(Exception):
    """Raised when input cannot be turned into records."""


@dataclass(frozen=True)
class Record:
    origin: str
    index: int
    text: str
    state: Mapping[str, Any]

    @property
    def is_whole_file(self) -> bool:
        return self.index == WHOLE_FILE_INDEX


def _line_state(line: str, parse_json: bool, origin: str, number: int) -> Mapping[str, Any]:
    if not parse_json:
        return {"record": line}
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError as exc:
        raise RecordError(f"{origin}: line {number} is not valid JSON ({exc.msg})") from exc
    # Jev wants a state object; scalars and arrays get a wrapper so they still travel.
    return parsed if isinstance(parsed, dict) else {"record": parsed}


def iter_lines(
    stream: TextIO, origin: str = STDIN_ORIGIN, parse_json: bool = False
) -> Iterator[Record]:
    """Yield one Record per non-blank line, keeping original line numbers."""
    for number, raw in enumerate(stream, start=1):
        line = raw.rstrip("\n").rstrip("\r")
        if not line.strip():
            continue  # blank lines cost a request and mean nothing
        yield Record(
            origin=origin,
            index=number,
            text=line,
            state=_line_state(line, parse_json, origin, number),
        )


def iter_file_lines(paths: Iterable[str], parse_json: bool = False) -> Iterator[Record]:
    """Yield line records across several files, tagged with the file they came from."""
    for path in paths:
        try:
            with open(path, encoding="utf-8") as handle:
                yield from iter_lines(handle, origin=path, parse_json=parse_json)
        except FileNotFoundError as exc:
            raise RecordError(f"{path}: no such file") from exc
        except IsADirectoryError as exc:
            raise RecordError(f"{path}: is a directory") from exc
        except UnicodeDecodeError as exc:
            raise RecordError(f"{path}: not valid UTF-8 text") from exc
        except OSError as exc:
            raise RecordError(f"{path}: {exc.strerror or exc}") from exc


def iter_files(paths: Iterable[str]) -> Iterator[Record]:
    """Yield one Record per file, carrying the whole file as the record state."""
    for path in paths:
        try:
            with open(path, encoding="utf-8") as handle:
                content = handle.read()
        except FileNotFoundError as exc:
            raise RecordError(f"{path}: no such file") from exc
        except IsADirectoryError as exc:
            raise RecordError(f"{path}: is a directory") from exc
        except UnicodeDecodeError as exc:
            raise RecordError(f"{path}: not valid UTF-8 text") from exc
        except OSError as exc:
            raise RecordError(f"{path}: {exc.strerror or exc}") from exc

        yield Record(
            origin=path,
            index=WHOLE_FILE_INDEX,
            text=content,
            state={"path": path, "content": content},
        )
