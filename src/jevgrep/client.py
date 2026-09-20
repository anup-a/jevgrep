"""HTTP client for the Jev evaluation endpoint."""

from __future__ import annotations

import asyncio
import os
import ssl
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx

from .config import Config, ConfigError
from .matcher import YES
from .records import Record

# The gateway rejects requests that do not pin both protocol and spec versions.
PROTOCOL_VERSION = "0.0.1"
SPECIFICATION_VERSION = "4"

REQUEST_TIMEOUT = 60.0
MAX_ATTEMPTS = 4
RETRY_BASE_DELAY = 0.5
MAX_RETRY_DELAY = 30.0
RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})

# Provider overload arrives as HTTP 200 with an error body, so status codes are not enough.
_TRANSIENT_MARKERS = (
    "high demand",
    "overloaded",
    "please retry",
    "try again",
    "temporarily unavailable",
    "rate limit",
    "timeout",
)


class ClientError(Exception):
    """Raised when the gateway fails or answers in a shape we cannot use."""


def parse_retry_after(headers: Mapping[str, str]) -> float | None:
    """Seconds the server asked us to wait, capped so one record cannot stall a whole run.

    Only the delta-seconds form is honoured; the HTTP-date form is rare here and not worth
    the clock-skew risk, so it is ignored rather than guessed at.
    """
    raw = headers.get("Retry-After") or headers.get("retry-after")
    if raw is None:
        return None
    try:
        seconds = float(raw)
    except (TypeError, ValueError):
        return None
    if seconds < 0:
        return None
    return min(seconds, MAX_RETRY_DELAY)


def is_transient(message: str) -> bool:
    """Whether an error message describes a condition worth retrying."""
    lowered = message.lower()
    return any(marker in lowered for marker in _TRANSIENT_MARKERS)


def build_verify(env: Mapping[str, str] | None = None) -> ssl.SSLContext | bool:
    """Trust settings for the HTTP client.

    httpx pins its own certifi bundle and ignores SSL_CERT_FILE, so behind a TLS-inspecting
    corporate proxy every request fails even though curl succeeds. Honour the standard
    variable (and a jevgrep-specific override) by building the context ourselves.
    Verification is never disabled -- an unusable bundle is an error, not a downgrade.
    """
    env = os.environ if env is None else env

    for name in ("JEVGREP_CA_BUNDLE", "SSL_CERT_FILE"):
        bundle = (env.get(name) or "").strip()
        if not bundle:
            continue
        if not Path(bundle).is_file():
            raise ConfigError(f"{name} points at {bundle!r}, which is not a readable file")
        try:
            return ssl.create_default_context(cafile=bundle)
        except OSError as exc:
            raise ConfigError(f"{name}={bundle!r} is not a usable CA bundle: {exc}") from exc

    return True


def build_proxy(env: Mapping[str, str] | None = None) -> str | None:
    """Proxy to route requests through, from environment variables only.

    httpx's trust_env also inherits the *macOS system* proxy setting, which on a dev machine
    is typically a local debugging proxy (Bifrost, Charles, mitmproxy). Those re-sign traffic
    with certificates OpenSSL 3 rejects, so API calls fail for reasons that have nothing to do
    with the API. Setting HTTPS_PROXY is a deliberate choice; a system-wide toggle is not.
    """
    env = os.environ if env is None else env

    for name in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        value = (env.get(name) or "").strip()
        if value:
            return value
    return None


def build_request(state: Mapping[str, Any], question: Mapping[str, Any], name: str) -> dict:
    return {"state": dict(state), "questions": {name: dict(question)}}


def build_headers(config: Config) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.api_key}",
        "ai-gateway-protocol-version": PROTOCOL_VERSION,
        "ai-evaluation-model-specification-version": SPECIFICATION_VERSION,
        "ai-model-id": config.model,
        "content-type": "application/json",
    }


def answer_confidence(payload: Mapping[str, Any], name: str) -> float | None:
    """Jev reports confidence separately from the answer, and omits it for booleans."""
    value = (
        ((payload.get("providerMetadata") or {}).get("typesafe") or {}).get("confidence") or {}
    ).get(name)
    return float(value) if isinstance(value, (int, float)) else None


def parse_answer(payload: Mapping[str, Any], name: str) -> tuple[float, float | None]:
    """Pull (probability, confidence) out of a gateway response body."""
    error = payload.get("error")
    if isinstance(error, Mapping):
        raise ClientError(str(error.get("message", error)))

    answer = (payload.get("answers") or {}).get(name)
    if not isinstance(answer, Mapping):
        raise ClientError(f"response carried no answer named {name!r}")

    probabilities = answer.get("probabilities")
    if isinstance(probabilities, Mapping):
        probability = probabilities.get(YES)
        if not isinstance(probability, (int, float)):
            raise ClientError(f"choice answer carried no {YES!r} option: {sorted(probabilities)}")
    else:
        probability = answer.get("probability")  # type=boolean answers look like this

    if not isinstance(probability, (int, float)):
        raise ClientError(f"answer of type {answer.get('type')!r} carried no probability")

    return float(probability), answer_confidence(payload, name)


def parse_score(payload: Mapping[str, Any], name: str) -> tuple[float, float | None]:
    """Pull (score, confidence) out of a `score` answer.

    The gateway's `score` is the expected value over the bucket distribution, so it is
    continuous and usable directly as a ranking key.
    """
    error = payload.get("error")
    if isinstance(error, Mapping):
        raise ClientError(str(error.get("message", error)))

    answer = (payload.get("answers") or {}).get(name)
    if not isinstance(answer, Mapping):
        raise ClientError(f"response carried no answer named {name!r}")

    score = answer.get("score")
    if not isinstance(score, (int, float)):
        raise ClientError(f"answer of type {answer.get('type')!r} carried no score")

    return float(score), answer_confidence(payload, name)


def parse_cost(payload: Mapping[str, Any]) -> float:
    """Market cost of one call in USD; the free window reports 0 for the billed cost."""
    gateway = (payload.get("providerMetadata") or {}).get("gateway") or {}
    try:
        return float(gateway.get("marketCost", 0.0))
    except (TypeError, ValueError):
        return 0.0


class JevClient:
    """Thin async wrapper. One record plus one question per request."""

    def __init__(self, config: Config, client: httpx.AsyncClient):
        self._config = config
        self._client = client
        self._cost = 0.0

    @property
    def spent(self) -> float:
        return self._cost

    async def evaluate(
        self, record: Record, question: Mapping[str, Any], name: str
    ) -> tuple[float, float | None]:
        """Probability that a yes/no question is true of the record, plus confidence."""
        return parse_answer(await self.ask(record.state, question, name), name)

    async def evaluate_score(
        self, record: Record, question: Mapping[str, Any], name: str
    ) -> tuple[float, float | None]:
        """Graded score for the record, plus confidence."""
        return parse_score(await self.ask(record.state, question, name), name)

    async def ask(
        self, state: Mapping[str, Any], question: Mapping[str, Any], name: str
    ) -> Mapping[str, Any]:
        """One question about one state, with retries. Returns the raw gateway payload."""
        body = build_request(state, question, name)
        last: Exception | None = None
        advised_delay: float | None = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            if attempt > 1:
                backoff = RETRY_BASE_DELAY * 2 ** (attempt - 2)
                await asyncio.sleep(advised_delay if advised_delay is not None else backoff)
                advised_delay = None

            try:
                response = await self._client.post(
                    self._config.endpoint,
                    headers=build_headers(self._config),
                    json=body,
                    timeout=REQUEST_TIMEOUT,
                )
            except httpx.HTTPError as exc:
                last = ClientError(f"request failed: {exc}")
                continue

            if response.status_code in RETRYABLE_STATUS:
                advised_delay = parse_retry_after(response.headers)
                waited = "" if advised_delay is None else f", retrying in {advised_delay:g}s"
                last = ClientError(f"gateway returned HTTP {response.status_code}{waited}")
                continue

            try:
                payload = response.json()
            except ValueError as exc:
                raise ClientError(f"gateway returned non-JSON body: {response.text[:200]}") from exc

            error = payload.get("error")
            if isinstance(error, Mapping):
                message = str(error.get("message", error))
                # Overload is reported as a 200 with an error body; a bad request is final.
                if not is_transient(message):
                    raise ClientError(message)
                last = ClientError(message)
                continue

            self._cost += parse_cost(payload)
            return payload

        raise last or ClientError("request failed for an unknown reason")
