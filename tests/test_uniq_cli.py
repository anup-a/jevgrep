"""jevuniq: collapse records that mean the same thing."""

import io

import pytest

from jevgrep import uniq_cli
from jevgrep.client import JevClient
from jevgrep.cluster import NEW_GROUP
from jevgrep.config import Config

CONFIG = Config(api_key="k", endpoint="https://example.test/evaluation-model", model="m")

TICKETS = "cannot log in\npassword reset email missing\ncheckout returns 500\nunable to sign in\n"


@pytest.fixture
def run(monkeypatch, capsys):
    """Drive the CLI with a scripted group choice per record text."""

    def _run(argv, stdin="", choices=None, confidence=0.9):
        table = choices or {}

        async def fake_ask(self, state, question, name):
            text = state.get("candidate", "")
            choice = table.get(text, NEW_GROUP)
            options = question["criteria"]
            if choice not in options:
                choice = NEW_GROUP
            return {
                "answers": {name: {"type": "choice", "choice": choice, "probabilities": {}}},
                "providerMetadata": {"typesafe": {"confidence": {name: confidence}}},
            }

        monkeypatch.setattr(JevClient, "ask", fake_ask)
        monkeypatch.setattr(uniq_cli, "read_config", lambda: CONFIG)
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
        code = uniq_cli.main(argv)
        cap = capsys.readouterr()
        return code, cap.out, cap.err

    return _run


def test_each_group_prints_its_first_member_once(run):
    code, out, _ = run([], stdin=TICKETS, choices={"unable to sign in": "g0"})

    assert code == 0
    assert out.splitlines() == [
        "cannot log in",
        "password reset email missing",
        "checkout returns 500",
    ]


def test_count_prefixes_group_sizes_like_uniq_c(run):
    _, out, _ = run(["-c"], stdin=TICKETS, choices={"unable to sign in": "g0"})

    assert out.splitlines()[0] == "      2 cannot log in"


def test_repeated_shows_only_groups_with_more_than_one_member(run):
    _, out, _ = run(["-d"], stdin=TICKETS, choices={"unable to sign in": "g0"})

    assert out.splitlines() == ["cannot log in"]


def test_unique_shows_only_groups_of_exactly_one(run):
    _, out, _ = run(["-u"], stdin=TICKETS, choices={"unable to sign in": "g0"})

    assert out.splitlines() == ["password reset email missing", "checkout returns 500"]


def test_nothing_collapses_when_every_record_is_distinct(run):
    _, out, _ = run([], stdin=TICKETS)

    assert len(out.splitlines()) == 4


def test_low_confidence_refuses_to_merge(run):
    _, out, _ = run(
        ["--min-confidence", "0.8"],
        stdin=TICKETS,
        choices={"unable to sign in": "g0"},
        confidence=0.2,
    )

    assert len(out.splitlines()) == 4


def test_empty_input_exits_one(run):
    code, out, _ = run([], stdin="")

    assert code == 1
    assert out == ""


def test_a_missing_file_exits_two(run, tmp_path):
    code, _, err = run([str(tmp_path / "nope.txt")])

    assert code == 2
    assert "nope.txt" in err


def test_stats_report_the_collapse(run):
    _, _, err = run(["--stats"], stdin=TICKETS, choices={"unable to sign in": "g0"})

    assert "4 records" in err and "3 groups" in err


def test_max_groups_must_be_positive(run):
    code, _, err = run(["--max-groups", "0"], stdin=TICKETS)

    assert code == 2
    assert "max-groups" in err.lower()
