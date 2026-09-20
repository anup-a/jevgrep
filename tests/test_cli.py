"""End-to-end CLI behaviour with the network call stubbed out."""

import io

import pytest

from jevgrep import cli
from jevgrep.config import Config

CONFIG = Config(api_key="sk-test", endpoint="https://example.test/evaluation-model", model="m")

EXIT_MATCH, EXIT_NO_MATCH, EXIT_ERROR = 0, 1, 2


@pytest.fixture
def run(monkeypatch, capsys):
    """Run the CLI against a scripted set of probabilities, keyed by record text."""

    def _run(argv, stdin="", probabilities=None, confidence=0.9):
        scores = probabilities or {}

        async def fake_evaluate(self, record, question, name):
            return scores.get(record.text, 0.0), confidence

        monkeypatch.setattr(cli.JevClient, "evaluate", fake_evaluate)
        monkeypatch.setattr(cli, "load_config", lambda env=None: CONFIG)
        monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
        code = cli.main(argv)
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    return _run


def test_matching_lines_are_printed_and_exit_zero(run):
    code, out, _ = run(
        ["is this a job posting?"],
        stdin="hiring a rust dev\nmy cat is asleep\n",
        probabilities={"hiring a rust dev": 0.95, "my cat is asleep": 0.02},
    )

    assert code == EXIT_MATCH
    assert out == "hiring a rust dev\n"


def test_no_matches_exits_one_like_grep(run):
    code, out, _ = run(["is this a job posting?"], stdin="my cat is asleep\n")

    assert code == EXIT_NO_MATCH
    assert out == ""


def test_invert_match_selects_the_complement(run):
    code, out, _ = run(
        ["-v", "is this a job posting?"],
        stdin="hiring a rust dev\nmy cat is asleep\n",
        probabilities={"hiring a rust dev": 0.95},
    )

    assert code == EXIT_MATCH
    assert out == "my cat is asleep\n"


def test_count_prints_only_the_number_of_matches(run):
    code, out, _ = run(
        ["-c", "pred"], stdin="a\nb\nc\n", probabilities={"a": 0.9, "b": 0.9, "c": 0.1}
    )

    assert code == EXIT_MATCH
    assert out == "2\n"


def test_quiet_prints_nothing_but_still_signals_via_exit_code(run):
    code, out, _ = run(["-q", "pred"], stdin="a\n", probabilities={"a": 0.9})

    assert code == EXIT_MATCH
    assert out == ""


def test_line_numbers_are_grep_shaped(run):
    _, out, _ = run(["-n", "pred"], stdin="a\nb\n", probabilities={"b": 0.9})

    assert out == "2:b\n"


def test_explain_shows_probability_and_confidence(run):
    _, out, _ = run(["--explain", "pred"], stdin="a\n", probabilities={"a": 0.91})

    assert out == "[p=0.91 c=0.90] a\n"


def test_threshold_is_respected(run):
    code, _, _ = run(["-t", "0.95", "pred"], stdin="a\n", probabilities={"a": 0.9})

    assert code == EXIT_NO_MATCH


def test_min_confidence_suppresses_uncertain_records(run):
    code, out, err = run(
        ["--min-confidence", "0.95", "pred"], stdin="a\n", probabilities={"a": 0.99}, confidence=0.4
    )

    assert code == EXIT_NO_MATCH
    assert out == ""
    assert "uncertain" in err.lower()


def test_whole_file_mode_prints_paths(run, tmp_path):
    target = tmp_path / "net.py"
    target.write_text("import socket\n")

    _, out, _ = run(["--whole", "pred", str(target)], probabilities={"import socket\n": 0.9})

    assert out == f"{target}\n"


def test_file_arguments_default_to_line_mode_with_origin_prefixes(run, tmp_path):
    first = tmp_path / "a.txt"
    first.write_text("alpha\nbeta\n")
    second = tmp_path / "b.txt"
    second.write_text("gamma\n")

    _, out, _ = run(["pred", str(first), str(second)], probabilities={"beta": 0.9, "gamma": 0.9})

    assert out == f"{first}:beta\n{second}:gamma\n"


def test_a_single_file_argument_has_no_origin_prefix(run, tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("alpha\nbeta\n")

    _, out, _ = run(["pred", str(target)], probabilities={"beta": 0.9})

    assert out == "beta\n"


def test_a_missing_file_exits_two_with_a_message(run, tmp_path):
    code, _, err = run(["pred", str(tmp_path / "nope.txt")])

    assert code == EXIT_ERROR
    assert "nope.txt" in err


def test_a_config_error_exits_two(monkeypatch, capsys):
    from jevgrep.config import ConfigError

    def boom(env=None):
        raise ConfigError("JEVGREP_API_KEY is not set")

    monkeypatch.setattr(cli, "load_config", boom)
    monkeypatch.setattr("sys.stdin", io.StringIO("a\n"))

    assert cli.main(["pred"]) == EXIT_ERROR
    assert "JEVGREP_API_KEY" in capsys.readouterr().err


def test_an_empty_predicate_exits_two(run):
    code, _, err = run(["   "], stdin="a\n")

    assert code == EXIT_ERROR
    assert err.strip() != ""


def test_files_with_matches_lists_each_origin_once(run, tmp_path):
    target = tmp_path / "a.txt"
    target.write_text("alpha\nbeta\n")

    _, out, _ = run(["-l", "pred", str(target)], probabilities={"alpha": 0.9, "beta": 0.9})

    assert out == f"{target}\n"


def test_stats_are_reported_on_stderr(run):
    _, _, err = run(["--stats", "pred"], stdin="a\nb\n", probabilities={"a": 0.9})

    assert "2 records" in err
