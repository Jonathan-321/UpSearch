"""QA-specific model execution — wraps ``complete_for_route`` with error handling,
provider metadata tagging, and clear degraded-mode semantics.

This helper ensures QA never silently claims strong-model verification when the
strong model was unavailable (missing key, no strong model configured, or the
call itself failed).
"""

from __future__ import annotations

from typing import Any

from .json_utils import parse_model_json_object
from .model_execution import complete_for_route
from .model_router import ModelRoute


_QADefaultResult = dict[str, Any]


def _degraded_result(error_reason: str, existing_flags: list[str]) -> dict[str, Any]:
    """Build a degraded-mode result dict with a clear marker."""
    return {
        "passed": False,
        "score": 5 if not existing_flags else 4,
        "flags": [f"QA model degraded: {error_reason}"] + existing_flags[:1],
        "recommendations": [
            "Configure a verification model or review this packet manually."
        ],
        "claim_check": "Not evaluated by a configured verification model.",
        "source_coverage": "Deterministic source checks only.",
    }


def qa_verify(
    route: ModelRoute,
    *,
    system: str,
    user_prompt: str,
    rule_flags: list[str],
    max_tokens: int = 512,
) -> tuple[dict[str, Any], bool]:
    """Execute a QA verification through ``route``.

    Returns a (result_dict, degraded) pair.

    *degraded* is ``True`` when the route is an unconfigured fallback, or the
    execution itself failed. Callers MUST write model_route metadata that
    respects this flag — when it is True the LLM result does NOT represent
    a strong-model evaluation.

    *result_dict* is the parsed JSON on success, or a degraded-mode result
    dict on failure.
    """
    if not route.configured:
        return _degraded_result(
            f"route not configured: {route.provider}/{route.model}", rule_flags
        ), True

    if route.is_fallback:
        return _degraded_result(
            f"using fallback route ({route.provider}/{route.model}) — strong model unavailable",
            rule_flags,
        ), True

    try:
        llm_text = complete_for_route(
            route,
            system=system,
            user=user_prompt,
            max_tokens=max_tokens,
        )
        llm_result: dict[str, Any] = parse_model_json_object(
            llm_text,
            {"passed": False, "score": 4, "flags": ["QA parse error"]},
        )
        return llm_result, False
    except Exception as exc:
        return _degraded_result(
            f"execution failed: {type(exc).__name__}", rule_flags
        ), True
