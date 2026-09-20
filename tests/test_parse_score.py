"""`score` answers. The question builder lives in jevutils; parsing stays here."""

import pytest

from jevgrep.client import ClientError, parse_score

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
