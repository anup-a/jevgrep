import json
import re

from jevgrep import colors
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
    defaults = {
        "line_numbers": False,
        "explain": False,
        "jsonl": False,
        "with_origin": False,
        "color": False,
    }
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


def test_colour_is_off_by_default_so_pipes_stay_clean():
    assert "\033[" not in format_verdict(verdict(), options(explain=True, with_origin=True))


def test_a_confident_value_is_painted_green():
    formatted = format_verdict(verdict(probability=0.98), options(explain=True, color=True))

    assert colors.CONFIDENT in formatted
    assert "0.98" in formatted


def test_an_unsure_confidence_is_painted_red():
    formatted = format_verdict(verdict(confidence=0.16), options(explain=True, color=True))

    assert colors.UNSURE in formatted


def test_a_middling_value_is_painted_amber():
    formatted = format_verdict(verdict(probability=0.75), options(explain=True, color=True))

    assert colors.WAVERING in formatted


def test_probability_and_confidence_are_coloured_independently():
    formatted = format_verdict(
        verdict(probability=0.99, confidence=0.20), options(explain=True, color=True)
    )

    assert colors.CONFIDENT in formatted and colors.UNSURE in formatted


def test_the_origin_is_painted_like_grep_paints_filenames():
    formatted = format_verdict(verdict(), options(with_origin=True, color=True))

    assert colors.ORIGIN in formatted


def test_the_line_number_is_painted_like_grep_paints_line_numbers():
    formatted = format_verdict(verdict(), options(line_numbers=True, color=True))

    assert colors.LINE_NUMBER in formatted


def test_a_whole_file_path_is_painted_as_an_origin():
    formatted = format_verdict(verdict(record=FILE), options(color=True))

    assert colors.ORIGIN in formatted and "src/net.py" in formatted


def test_jsonl_output_is_never_coloured_because_it_must_stay_parseable():
    raw = format_verdict(verdict(), options(jsonl=True, color=True))

    assert "\033[" not in raw
    assert json.loads(raw)["probability"] == 0.92


def test_stripping_the_escapes_leaves_exactly_the_uncoloured_output():
    plain = format_verdict(verdict(), options(explain=True, line_numbers=True))
    painted = format_verdict(verdict(), options(explain=True, line_numbers=True, color=True))

    assert re.sub(r"\033\[[0-9;]*m", "", painted) == plain
