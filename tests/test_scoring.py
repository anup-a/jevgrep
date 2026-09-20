"""Graded `score` questions, used by jevsort to rank records."""

import pytest

from jevgrep.client import ClientError, parse_score
from jevgrep.scoring import DEFAULT_STEPS, build_score_question

# Copied from a real gateway response: note `score` is the expected value over the
# bucket distribution (0.01*3 + 0.99*4), not the argmax bucket index.
REAL = {
    "answers": {
        "rank": {
            "type": "score",
            "score": 3.98,
            "probabilities": {"0": 0, "1": 0, "2": 0, "3": 0.01, "4": 0.99},
        }
    },
    "providerMetadata": {"typesafe": {"confidence": {"rank": 0.99}}},
}


def test_parses_score_and_confidence():
    assert parse_score(REAL, "rank") == (3.98, 0.99)


def test_confidence_may_be_absent():
    payload = {"answers": {"rank": {"type": "score", "score": 1.5}}}

    assert parse_score(payload, "rank") == (1.5, None)


def test_a_missing_answer_is_an_error():
    with pytest.raises(ClientError):
        parse_score({"answers": {}}, "rank")


def test_an_answer_without_a_score_is_an_error():
    payload = {"answers": {"rank": {"type": "choice", "probabilities": {"yes": 1}}}}

    with pytest.raises(ClientError):
        parse_score(payload, "rank")


def test_a_gateway_error_body_surfaces_its_message():
    with pytest.raises(ClientError, match="expected array"):
        parse_score({"error": {"message": "Invalid input: expected array"}}, "rank")


def test_question_is_a_score_with_array_criteria():
    # The gateway rejects score questions whose criteria is an object, and the array
    # length is what defines the bucket range.
    body = build_score_question("how urgent is this?", steps=5)

    assert body["type"] == "score"
    assert isinstance(body["criteria"], list)
    assert len(body["criteria"]) == 5
    assert "how urgent is this?" in body["instructions"]


def test_default_steps_are_used_when_unspecified():
    assert len(build_score_question("how urgent?")["criteria"]) == DEFAULT_STEPS


def test_criteria_label_both_ends_of_the_scale():
    criteria = build_score_question("how urgent?", steps=5)["criteria"]

    assert criteria[0].startswith("0")
    assert criteria[-1].startswith("4")


@pytest.mark.parametrize("steps", [1, 0, -3, 11])
def test_absurd_scales_are_rejected(steps):
    with pytest.raises(ValueError):
        build_score_question("how urgent?", steps=steps)


def test_an_empty_question_is_rejected():
    with pytest.raises(ValueError):
        build_score_question("   ")
