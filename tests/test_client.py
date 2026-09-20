import pytest

from jevgrep.client import ClientError, build_request, parse_answer

# Shapes below are copied from real gateway responses, not invented.
REAL_RESPONSE = {
    "answers": {
        "match": {"type": "choice", "choice": "no", "probabilities": {"yes": 0.33, "no": 0.67}}
    },
    "usage": {"inputTokens": 585, "outputTokens": 94},
    "providerMetadata": {
        "typesafe": {"confidence": {"match": 0.82}},
        "gateway": {"marketCost": "0.00002457"},
    },
}


def test_parses_probability_and_confidence():
    assert parse_answer(REAL_RESPONSE, "match") == (0.33, 0.82)


def test_confidence_is_none_when_the_provider_omits_it():
    payload = {"answers": {"match": {"type": "choice", "probabilities": {"yes": 0.9, "no": 0.1}}}}

    assert parse_answer(payload, "match") == (0.9, None)


def test_a_boolean_answer_is_still_understood():
    # The gateway answers type=boolean if asked; it just never carries confidence.
    payload = {"answers": {"match": {"type": "boolean", "probability": 0.42}}}

    assert parse_answer(payload, "match") == (0.42, None)


def test_a_choice_answer_missing_the_yes_option_is_a_client_error():
    payload = {"answers": {"match": {"type": "choice", "probabilities": {"maybe": 1.0}}}}

    with pytest.raises(ClientError):
        parse_answer(payload, "match")


def test_a_missing_answer_is_a_client_error():
    with pytest.raises(ClientError):
        parse_answer({"answers": {}}, "match")


def test_a_gateway_error_body_is_a_client_error_carrying_the_message():
    body = {"error": {"message": "Invalid input: expected array", "type": "invalid_request_error"}}

    with pytest.raises(ClientError) as excinfo:
        parse_answer(body, "match")

    assert "Invalid input: expected array" in str(excinfo.value)


def test_an_answer_with_no_usable_probability_is_a_client_error():
    payload = {"answers": {"match": {"type": "score", "score": 3.0}}}

    with pytest.raises(ClientError):
        parse_answer(payload, "match")


def test_market_cost_is_read_from_provider_metadata():
    from jevgrep.client import parse_cost

    assert parse_cost(REAL_RESPONSE) == pytest.approx(0.00002457)


def test_market_cost_is_zero_when_absent():
    from jevgrep.client import parse_cost

    assert parse_cost({"answers": {}}) == 0.0


def test_request_body_pairs_the_record_state_with_the_question():
    body = build_request(state={"record": "alpha"}, question={"type": "boolean"}, name="match")

    assert body == {"state": {"record": "alpha"}, "questions": {"match": {"type": "boolean"}}}
