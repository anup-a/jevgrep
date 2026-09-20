"""A 429 carries Retry-After; exponential backoff that ignores it just burns the quota."""

import httpx

from jevgrep.client import MAX_RETRY_DELAY, JevClient, parse_retry_after
from jevgrep.config import Config
from jevgrep.records import Record

CONFIG = Config(api_key="k", endpoint="https://example.test/evaluation-model", model="m")
RECORD = Record(origin="x", index=1, text="t", state={"record": "t"})
QUESTION = {"type": "choice", "instructions": "i", "criteria": {"yes": "y", "no": "n"}}
OK = {"answers": {"match": {"type": "choice", "probabilities": {"yes": 0.9, "no": 0.1}}}}


def test_no_header_means_no_advice():
    assert parse_retry_after({}) is None


def test_a_numeric_header_is_read_as_seconds():
    assert parse_retry_after({"Retry-After": "7"}) == 7.0


def test_a_fractional_header_is_read():
    assert parse_retry_after({"retry-after": "1.5"}) == 1.5


def test_an_unparseable_header_is_ignored_rather_than_crashing():
    assert parse_retry_after({"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}) is None


def test_a_negative_header_is_ignored():
    assert parse_retry_after({"Retry-After": "-5"}) is None


def test_an_absurd_header_is_capped_so_one_record_cannot_stall_the_run():
    assert parse_retry_after({"Retry-After": "86400"}) == MAX_RETRY_DELAY


async def test_the_client_waits_for_the_advised_delay_before_retrying(monkeypatch):
    slept: list[float] = []

    async def record_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr("jevgrep.client.asyncio.sleep", record_sleep)

    responses = [
        httpx.Response(429, headers={"Retry-After": "3"}, json={"error": {"message": "slow down"}}),
        httpx.Response(200, json=OK),
    ]
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: responses.pop(0)))

    await JevClient(CONFIG, http).evaluate(RECORD, QUESTION, "match")

    assert slept == [3.0]


async def test_without_the_header_it_falls_back_to_exponential_backoff(monkeypatch):
    slept: list[float] = []

    async def record_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr("jevgrep.client.asyncio.sleep", record_sleep)

    responses = [httpx.Response(503, json={}), httpx.Response(200, json=OK)]
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: responses.pop(0)))

    await JevClient(CONFIG, http).evaluate(RECORD, QUESTION, "match")

    assert slept and slept[0] > 0
