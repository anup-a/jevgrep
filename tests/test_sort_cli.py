"""jevsort: rank records by a graded question."""

import io

import pytest

from jevgrep import sort_cli
from jevgrep.client import JevClient
from jevgrep.config import Config

CONFIG = Config(api_key="k", endpoint="https://example.test/evaluation-model", model="m")


@pytest.fixture
def run(monkeypatch, capsys):
    def _run(argv, stdin="", scores=None, confidence=0.9):
        table = scores or {}

        async def fake(self, record, question, name):
            return table.get(record.text, 0.0), confidence

        monkeypatch.setattr(JevClient, "evaluate_score", fake)
        monkeypatch.setattr(sort_cli, "read_config", lambda: CONFIG)
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
        code = sort_cli.main(argv)
        cap = capsys.readouterr()
        return code, cap.out, cap.err

    return _run


TICKETS = "disk almost full\nprod is down\ntypo in footer\n"
SCORES = {"prod is down": 4.0, "disk almost full": 2.5, "typo in footer": 0.2}


def test_highest_scoring_record_comes_first(run):
    code, out, _ = run(["how urgent?"], stdin=TICKETS, scores=SCORES)

    assert code == 0
    assert out.splitlines() == ["prod is down", "disk almost full", "typo in footer"]


def test_reverse_flips_the_order(run):
    _, out, _ = run(["-r", "how urgent?"], stdin=TICKETS, scores=SCORES)

    assert out.splitlines() == ["typo in footer", "disk almost full", "prod is down"]


def test_top_truncates_to_the_n_highest(run):
    _, out, _ = run(["--top", "2", "how urgent?"], stdin=TICKETS, scores=SCORES)

    assert out.splitlines() == ["prod is down", "disk almost full"]


def test_explain_shows_the_score(run):
    _, out, _ = run(["--explain", "how urgent?"], stdin="prod is down\n", scores=SCORES)

    assert out.startswith("[4.00 c=0.90]")


def test_empty_input_exits_one(run):
    code, out, _ = run(["how urgent?"], stdin="")

    assert code == 1
    assert out == ""


def test_an_empty_question_exits_two(run):
    code, _, err = run(["   "], stdin=TICKETS)

    assert code == 2
    assert err.strip()


def test_an_out_of_range_scale_exits_two(run):
    code, _, err = run(["--scale", "99", "how urgent?"], stdin=TICKETS)

    assert code == 2
    assert "scale" in err.lower()


def test_a_missing_file_exits_two(run, tmp_path):
    code, _, err = run(["how urgent?", str(tmp_path / "nope.txt")])

    assert code == 2
    assert "nope.txt" in err


def test_ties_keep_input_order(run):
    _, out, _ = run(["how urgent?"], stdin="alpha\nbeta\n", scores={"alpha": 1.0, "beta": 1.0})

    assert out.splitlines() == ["alpha", "beta"]


def test_jsonl_output_carries_scores(run):
    import json

    _, out, _ = run(["--jsonl", "how urgent?"], stdin="prod is down\n", scores=SCORES)
    payload = json.loads(out.strip())

    assert payload["score"] == 4.0
    assert payload["text"] == "prod is down"


def test_stats_go_to_stderr(run):
    _, _, err = run(["--stats", "how urgent?"], stdin=TICKETS, scores=SCORES)

    assert "3 records" in err
