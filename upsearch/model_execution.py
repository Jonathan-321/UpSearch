"""Execute a completion against an explicit model route.

Reliability features
--------------------
Provider clients are cached (one per provider) so connection pools are reused
across the 7-step pipeline instead of being rebuilt on every call. Each network
call is wrapped in an exponential-backoff retry loop that only retries
*transient* failures (HTTP 429 rate limits, 5xx/408 server errors, and
connection/timeout errors). Auth errors (401/403) and other non-retryable
client errors (400/404/422, ...) are surfaced immediately.

Tunable knobs (module constants, each overridable via an env var so tests can
set delays to 0 for speed):

- ``MODEL_RETRY_MAX_ATTEMPTS`` (default 3) — total attempts, including the first.
- ``MODEL_RETRY_BASE_DELAY``   (default 0.5) — base backoff seconds; also the
  upper bound of the added random jitter.
- ``MODEL_RETRY_MAX_DELAY``    (default 8.0) — cap on the backoff delay.
- ``MODEL_REQUEST_TIMEOUT``    (default 60.0) — per-request timeout (seconds)
  handed to each provider SDK client.
"""

from __future__ import annotations

import os
import random
import threading
import time
from typing import Callable, TypeVar

from .model_router import ModelRoute


_DS_MODELS = frozenset({"deepseek-chat", "deepseek-reasoner"})

# --- Retry / timeout configuration -----------------------------------------

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BASE_DELAY = 0.5
DEFAULT_MAX_DELAY = 8.0
DEFAULT_REQUEST_TIMEOUT = 60.0

ENV_MAX_ATTEMPTS = "MODEL_RETRY_MAX_ATTEMPTS"
ENV_BASE_DELAY = "MODEL_RETRY_BASE_DELAY"
ENV_MAX_DELAY = "MODEL_RETRY_MAX_DELAY"
ENV_REQUEST_TIMEOUT = "MODEL_REQUEST_TIMEOUT"

T = TypeVar("T")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _max_attempts() -> int:
    return max(1, _env_int(ENV_MAX_ATTEMPTS, DEFAULT_MAX_ATTEMPTS))


def _base_delay() -> float:
    return max(0.0, _env_float(ENV_BASE_DELAY, DEFAULT_BASE_DELAY))


def _max_delay() -> float:
    return max(0.0, _env_float(ENV_MAX_DELAY, DEFAULT_MAX_DELAY))


def _request_timeout() -> float:
    return max(0.0, _env_float(ENV_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT))


# --- Transient-error classification ----------------------------------------

# Matched against the lowercased exception class name when no HTTP status code is
# available (e.g. connection/timeout errors carry no status code).
_RETRYABLE_NAME_HINTS = (
    "ratelimit",
    "timeout",
    "apiconnection",
    "connection",
    "internalserver",
    "serviceunavailable",
)
_NON_RETRYABLE_NAME_HINTS = (
    "authentication",
    "permissiondenied",
    "badrequest",
    "notfound",
    "unprocessable",
    "conflict",
    "invalidrequest",
)


def _status_code(exc: BaseException) -> int | None:
    code = getattr(exc, "status_code", None)
    if isinstance(code, int):
        return code
    response = getattr(exc, "response", None)
    code = getattr(response, "status_code", None)
    if isinstance(code, int):
        return code
    return None


def _is_retryable(exc: BaseException) -> bool:
    """True only for transient failures worth retrying."""
    code = _status_code(exc)
    if code is not None:
        if code == 429 or code == 408:
            return True
        return code >= 500
    name = type(exc).__name__.lower()
    if any(hint in name for hint in _NON_RETRYABLE_NAME_HINTS):
        return False
    if any(hint in name for hint in _RETRYABLE_NAME_HINTS):
        return True
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    return False


def _retry(fn: Callable[[], T]) -> T:
    """Call ``fn`` with exponential backoff + jitter for transient errors."""
    attempts = _max_attempts()
    base = _base_delay()
    cap = _max_delay()
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — classified below
            last_exc = exc
            if attempt >= attempts or not _is_retryable(exc):
                raise
            delay = min(cap, base * (2 ** (attempt - 1))) + random.uniform(0, base)
            if delay > 0:
                time.sleep(delay)
    # Loop always returns or raises; this satisfies type checkers.
    assert last_exc is not None
    raise last_exc


# --- Cached provider clients -----------------------------------------------

_CLIENTS: dict[str, object] = {}
_CLIENT_LOCK = threading.Lock()


def _build_client(provider: str) -> object:
    timeout = _request_timeout()
    if provider == "deepseek":
        from openai import OpenAI

        return OpenAI(
            api_key=os.environ.get("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com/v1",
            timeout=timeout,
            max_retries=0,
        )
    if provider == "openai":
        from openai import OpenAI

        return OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            timeout=timeout,
            max_retries=0,
        )
    if provider == "openrouter":
        from openai import OpenAI

        return OpenAI(
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
            timeout=timeout,
            max_retries=0,
        )
    if provider in {"anthropic", "claude"}:
        import anthropic

        return anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
            timeout=timeout,
            max_retries=0,
        )
    raise RuntimeError(f"Unsupported model provider: {provider}")


def _get_client(provider: str) -> object:
    """Return a cached client for ``provider``, building it once under a lock."""
    client = _CLIENTS.get(provider)
    if client is not None:
        return client
    with _CLIENT_LOCK:
        client = _CLIENTS.get(provider)
        if client is None:
            client = _build_client(provider)
            _CLIENTS[provider] = client
        return client


def _reset_clients() -> None:
    """Drop all cached clients. Primarily for tests."""
    with _CLIENT_LOCK:
        _CLIENTS.clear()


# --- Public entry point -----------------------------------------------------


def _complete_openai_style(
    provider: str, model: str, *, system: str, user: str, max_tokens: int
) -> str:
    client = _get_client(provider)

    def _do() -> str:
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (response.choices[0].message.content or "").strip()

    return _retry(_do)


def complete_for_route(
    route: ModelRoute,
    *,
    system: str,
    user: str,
    max_tokens: int = 1024,
) -> str:
    if not route.configured:
        raise RuntimeError(f"Model route is not configured: {route.provider}/{route.model}")

    provider = route.provider.lower()

    if provider == "deepseek":
        model = os.environ.get("DEEPSEEK_MODEL", route.model)
        if model not in _DS_MODELS:
            model = "deepseek-chat"
        return _complete_openai_style(
            provider, model, system=system, user=user, max_tokens=max_tokens
        )

    if provider in {"anthropic", "claude"}:
        client = _get_client(provider)

        def _do() -> str:
            response = client.messages.create(
                model=route.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return response.content[0].text.strip()

        return _retry(_do)

    if provider in {"openai", "openrouter"}:
        return _complete_openai_style(
            provider, route.model, system=system, user=user, max_tokens=max_tokens
        )

    raise RuntimeError(f"Unsupported model provider: {route.provider}")
