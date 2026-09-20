import asyncio

import pytest

from jevgrep.concurrency import map_ordered


async def collect(items, func, limit):
    return [result async for result in map_ordered(items, func, limit=limit)]


async def test_results_come_back_in_input_order_despite_uneven_latency():
    async def slow_for_early_items(n):
        await asyncio.sleep((10 - n) / 1000)
        return n

    assert await collect(range(10), slow_for_early_items, limit=4) == list(range(10))


async def test_never_exceeds_the_concurrency_limit():
    in_flight = 0
    peak = 0

    async def track(n):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.005)
        in_flight -= 1
        return n

    await collect(range(20), track, limit=3)

    assert peak <= 3


async def test_empty_input_yields_nothing():
    async def identity(n):
        return n

    assert await collect([], identity, limit=4) == []


async def test_fewer_items_than_the_limit_still_works():
    async def identity(n):
        return n

    assert await collect([1, 2], identity, limit=8) == [1, 2]


async def test_an_exception_propagates_to_the_caller():
    async def boom(n):
        if n == 3:
            raise RuntimeError("boom")
        return n

    with pytest.raises(RuntimeError):
        await collect(range(10), boom, limit=4)


async def test_limit_must_be_positive():
    async def identity(n):
        return n

    with pytest.raises(ValueError):
        await collect([1], identity, limit=0)


async def test_it_pulls_lazily_from_the_source():
    pulled = []

    def source():
        for n in range(100):
            pulled.append(n)
            yield n

    async def identity(n):
        await asyncio.sleep(0.001)
        return n

    results = []
    async for result in map_ordered(source(), identity, limit=4):
        results.append(result)
        if len(results) == 5:
            break

    assert len(pulled) < 100
