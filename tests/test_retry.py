"""The gateway reports provider overload as HTTP 200 with an error body, not a 5xx."""

import httpx
import pytest

from jevgrep.client import ClientError, JevClient, is_transient
from jevgrep.config import Config
from jevgrep.records import Record

CONFIG = Config(api_key="k", endpoint="https://example.test/evaluation-model", model="m")
RECORD = Record(origin="x", index=1, text="t", state={"record": "t"})
QUESTION = {"type": "choice", "instructions": "i", "criteria": {"yes": "y", "no": "n"}}

OK = {
    "answers": {"match": {"type": "choice", "probabilities": {"yes": 0.9, "no": 0.1}}},
    "providerMetadata": {
        "typesafe": {"confidence": {"match": 0.8}},
        "gateway": {"marketCost": "0.00001"},
    },
}
BUSY = {"error": {"message": "The upstream provider is currently experiencing high demand."}}
PERMANENT = {"error": {"message": "Invalid input: expected array, received undefined"}}


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr("jevgrep.client.RETRY_BASE_DELAY", 0.0)


def client_returning(*bodies: dict) -> tuple[JevClient, list[int]]:
    """A JevClient whose transport returns each body in turn, counting requests."""
    calls = [0]
    queue = list(bodies)

    def handler(request: httpx.Request) -> httpx.Response:
        calls[0] += 1
        return httpx.Response(200, json=queue.pop(0) if queue else bodies[-1])

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return JevClient(CONFIG, http), calls


def test_is_transient_recognises_provider_overload():
    assert is_transient("The upstream provider is currently experiencing high demand.")


def test_is_transient_rejects_a_validation_error():
    assert not is_transient("Invalid input: expected array, received undefined")


async def test_a_busy_response_is_retried_and_then_succeeds():
    client, calls = client_returning(BUSY, BUSY, OK)

    assert await client.evaluate(RECORD, QUESTION, "match") == (0.9, 0.8)
    assert calls[0] == 3


async def test_a_permanent_error_is_not_retried():
    client, calls = client_returning(PERMANENT)

    with pytest.raises(ClientError, match="Invalid input"):
        await client.evaluate(RECORD, QUESTION, "match")

    assert calls[0] == 1


async def test_retries_are_bounded_and_the_last_error_surfaces():
    client, calls = client_returning(BUSY)

    with pytest.raises(ClientError, match="high demand"):
        await client.evaluate(RECORD, QUESTION, "match")

    assert calls[0] > 1


async def test_cost_is_only_counted_for_the_successful_attempt():
    client, _ = client_returning(BUSY, OK)

    await client.evaluate(RECORD, QUESTION, "match")

    assert client.spent == pytest.approx(0.00001)
