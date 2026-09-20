import dataclasses
import io

import pytest

from jevgrep.records import RecordError, iter_files, iter_lines

STDIN = "(standard input)"


def test_iter_lines_numbers_records_from_one():
    records = list(iter_lines(io.StringIO("alpha\nbeta\n"), origin=STDIN))

    assert [(r.index, r.text) for r in records] == [(1, "alpha"), (2, "beta")]
    assert all(r.origin == STDIN for r in records)


def test_iter_lines_keeps_line_numbers_stable_when_skipping_blanks():
    records = list(iter_lines(io.StringIO("alpha\n\n   \nbeta\n"), origin=STDIN))

    assert [(r.index, r.text) for r in records] == [(1, "alpha"), (4, "beta")]


def test_iter_lines_wraps_plain_text_as_record_state():
    (record,) = list(iter_lines(io.StringIO("hello\n"), origin=STDIN))

    assert record.state == {"record": "hello"}


def test_iter_lines_parses_json_into_state():
    stream = io.StringIO('{"title":"Senior Rust dev","company":"Acme"}\n')

    (record,) = list(iter_lines(stream, origin=STDIN, parse_json=True))

    assert record.state == {"title": "Senior Rust dev", "company": "Acme"}
    assert record.text == '{"title":"Senior Rust dev","company":"Acme"}'


def test_iter_lines_rejects_malformed_json_with_line_number():
    stream = io.StringIO('{"ok":1}\nnot json at all\n')

    with pytest.raises(RecordError) as excinfo:
        list(iter_lines(stream, origin=STDIN, parse_json=True))

    assert "line 2" in str(excinfo.value)


def test_iter_lines_wraps_non_object_json_under_record_key():
    (record,) = list(iter_lines(io.StringIO("[1, 2, 3]\n"), origin=STDIN, parse_json=True))

    assert record.state == {"record": [1, 2, 3]}


def test_iter_files_yields_one_record_per_file(tmp_path):
    first = tmp_path / "a.py"
    first.write_text("import socket\n")
    second = tmp_path / "b.py"
    second.write_text("print('hi')\n")

    records = list(iter_files([str(first), str(second)]))

    assert [r.origin for r in records] == [str(first), str(second)]
    assert [r.index for r in records] == [0, 0]
    assert records[0].state == {"path": str(first), "content": "import socket\n"}


def test_iter_files_raises_record_error_for_missing_file(tmp_path):
    with pytest.raises(RecordError) as excinfo:
        list(iter_files([str(tmp_path / "nope.py")]))

    assert "nope.py" in str(excinfo.value)


def test_iter_files_raises_record_error_for_undecodable_file(tmp_path):
    binary = tmp_path / "blob.bin"
    binary.write_bytes(b"\xff\xfe\x00\x01")

    with pytest.raises(RecordError):
        list(iter_files([str(binary)]))


def test_records_are_immutable():
    (record,) = list(iter_lines(io.StringIO("alpha\n"), origin=STDIN))

    with pytest.raises(dataclasses.FrozenInstanceError):
        record.text = "mutated"
