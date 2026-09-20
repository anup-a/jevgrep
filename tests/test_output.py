import json

from jevgrep.matcher import Verdict
from jevgrep.output import OutputOptions, format_verdict
from jevgrep.records import Record

LINE = Record(origin="(standard input)", index=3, text="alpha", state={"record": "alpha"})
FILE = Record(origin="src/net.py", index=0, text="import socket\n", state={})


def verdict(record=LINE, probability=0.92, confidence=0.81) -> Verdict:
    return Verdict(
        record=record, probability=probability, confidence=confidence, matched=True, uncertain=False
    )


def options(**overrides) -> OutputOptions:
    defaults = {"line_numbers": False, "explain": False, "jsonl": False, "with_origin": False}
    return OutputOptions(**{**defaults, **overrides})


def test_default_line_output_is_just_the_record_text():
    assert format_verdict(verdict(), options()) == "alpha"


def test_line_numbers_prefix_grep_style():
    assert format_verdict(verdict(), options(line_numbers=True)) == "3:alpha"


def test_origin_prefix_grep_style():
    assert format_verdict(verdict(), options(with_origin=True)) == "(standard input):alpha"


def test_origin_and_line_numbers_combine_grep_style():
    formatted = format_verdict(verdict(), options(with_origin=True, line_numbers=True))

    assert formatted == "(standard input):3:alpha"


def test_explain_prefixes_probability_and_confidence():
    assert format_verdict(verdict(), options(explain=True)) == "[p=0.92 c=0.81] alpha"


def test_explain_renders_a_missing_confidence_as_a_dash():
    formatted = format_verdict(verdict(confidence=None), options(explain=True))

    assert formatted == "[p=0.92 c=-] alpha"


def test_whole_file_records_print_the_path_not_the_content():
    assert format_verdict(verdict(record=FILE), options()) == "src/net.py"


def test_whole_file_records_ignore_the_line_number_prefix():
    assert format_verdict(verdict(record=FILE), options(line_numbers=True)) == "src/net.py"


def test_jsonl_output_carries_the_full_verdict():
    payload = json.loads(format_verdict(verdict(), options(jsonl=True)))

    assert payload == {
        "origin": "(standard input)",
        "line": 3,
        "text": "alpha",
        "probability": 0.92,
        "confidence": 0.81,
        "matched": True,
        "uncertain": False,
    }


def test_jsonl_output_omits_the_line_number_for_whole_file_records():
    payload = json.loads(format_verdict(verdict(record=FILE), options(jsonl=True)))

    assert payload["line"] is None
    assert payload["origin"] == "src/net.py"
