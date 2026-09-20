import pytest

from jevgrep.matcher import MatchOptions, build_question, decide
from jevgrep.records import Record

RECORD = Record(origin="(standard input)", index=1, text="alpha", state={"record": "alpha"})


def options(**overrides) -> MatchOptions:
    defaults = {"threshold": 0.5, "min_confidence": 0.0, "invert": False}
    return MatchOptions(**{**defaults, **overrides})


def test_probability_above_threshold_matches():
    verdict = decide(RECORD, probability=0.92, confidence=0.8, options=options())

    assert verdict.matched is True
    assert verdict.uncertain is False
    assert verdict.probability == 0.92


def test_probability_below_threshold_does_not_match():
    assert decide(RECORD, probability=0.31, confidence=0.9, options=options()).matched is False


def test_probability_exactly_at_threshold_matches():
    verdict = decide(RECORD, probability=0.5, confidence=0.9, options=options(threshold=0.5))

    assert verdict.matched is True


def test_invert_flips_the_match():
    verdict = decide(RECORD, probability=0.92, confidence=0.8, options=options(invert=True))

    assert verdict.matched is False
    assert decide(RECORD, probability=0.1, confidence=0.8, options=options(invert=True)).matched


def test_low_confidence_is_uncertain_and_never_matches():
    verdict = decide(RECORD, probability=0.99, confidence=0.4, options=options(min_confidence=0.6))

    assert verdict.uncertain is True
    assert verdict.matched is False


def test_low_confidence_never_matches_under_invert_either():
    verdict = decide(
        RECORD, probability=0.01, confidence=0.4, options=options(min_confidence=0.6, invert=True)
    )

    assert verdict.uncertain is True
    assert verdict.matched is False


def test_missing_confidence_is_not_uncertain_when_no_floor_is_set():
    verdict = decide(RECORD, probability=0.92, confidence=None, options=options())

    assert verdict.uncertain is False
    assert verdict.matched is True


def test_missing_confidence_is_uncertain_when_a_floor_is_set():
    verdict = decide(RECORD, probability=0.92, confidence=None, options=options(min_confidence=0.6))

    assert verdict.uncertain is True


@pytest.mark.parametrize("probability", [-0.01, 1.01])
def test_out_of_range_probability_is_rejected(probability):
    with pytest.raises(ValueError):
        decide(RECORD, probability=probability, confidence=0.8, options=options())


def test_build_question_uses_a_two_way_choice_carrying_the_predicate():
    # Deliberately not type=boolean: the gateway returns no confidence for boolean answers,
    # which would make --min-confidence a no-op. A two-way choice returns both.
    body = build_question("is this a job posting?")

    assert body["type"] == "choice"
    assert "is this a job posting?" in body["instructions"]
    assert set(body["criteria"]) == {"yes", "no"}


def test_build_question_rejects_an_empty_predicate():
    with pytest.raises(ValueError):
        build_question("   ")
