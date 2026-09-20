"""Bounded, order-preserving, lazily-pulling async map."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")

_EXHAUSTED = object()


async def map_ordered(
    items: Iterable[T], func: Callable[[T], Awaitable[R]], limit: int
) -> AsyncIterator[R]:
    """Apply func across items with at most `limit` in flight, yielding in input order.

    The source is pulled lazily, one item per completed result, so this stays usable on an
    endless stdin stream. Cancelling the consumer cancels whatever is still in flight.
    """
    if limit < 1:
        raise ValueError(f"limit must be at least 1, got {limit}")

    source = iter(items)
    in_flight: deque[asyncio.Task[R]] = deque()

    def start_next() -> bool:
        nxt = next(source, _EXHAUSTED)
        if nxt is _EXHAUSTED:
            return False
        in_flight.append(asyncio.ensure_future(func(nxt)))  # type: ignore[arg-type]
        return True

    try:
        while len(in_flight) < limit and start_next():
            pass

        while in_flight:
            result = await in_flight.popleft()
            start_next()
            yield result
    finally:
        for task in in_flight:
            task.cancel()
        if in_flight:
            await asyncio.gather(*in_flight, return_exceptions=True)
