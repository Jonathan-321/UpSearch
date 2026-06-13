"""Regression tests for trace-state behavior in evaluate_packet.

Tests cover omitted, empty, partial, full, and errored traces.
"""

from upsearch.packet_checkup import agent_step, evaluate_packet, handoff_event, EXPECTED_AGENTS


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_full_trace(*, overrides: dict[str, str] | None = None) -> list[dict]:
    """Build a trace containing all 7 agent steps and 6 handoffs.

    Each agent step can have its status overridden (e.g. ``{"qa_verification": "error"}``).
    """
    overrides = overrides or {}
    events: list[dict] = []

    for agent in EXPECTED_AGENTS:
        events.append(
            agent_step(
                agent=agent,
                role="writer",
                reads=["company_brief"],
                writes=[f"{agent}_output"],
                output_summary=f"{agent} completed",
                status=overrides.get(agent, "ok"),
            )
        )

    for i in range(len(EXPECTED_AGENTS) - 1):
        events.append(
            handoff_event(
                from_agent=EXPECTED_AGENTS[i],
                to_agent=EXPECTED_AGENTS[i + 1],
                payload_keys=["packet"],
                reason="next stage",
            )
        )

    return events


# ── Fixtures (module-level for re-use) ───────────────────────────────────────


PACKET = {
    "technical_note": " ".join(["technical"] * 300),
    "outreach_drafts": {"email": "A concise outreach draft."},
    "qa_score": 9,
    "qa_flags": [],
}

PROBLEMS = [
    {
        "title": "Serving latency on XYZ",
        "source_urls": ["https://example.com/problem"],
        "relevance_score": 8,
    }
]

PEOPLE = [
    {
        "name": "Taylor Kim",
        "source_url": "https://example.com/taylor",
        "verification_status": "verified",
        "relevance_score": 8,
    }
]


# ── Tests ────────────────────────────────────────────────────────────────────


def test_omitted_trace_is_unavailable_and_no_coordination_failure() -> None:
    """No trace argument -> trace_status='unavailable', no agent_coordination_failure."""
    result = evaluate_packet("AcmeFlow", PACKET, PROBLEMS, PEOPLE)

    assert result["trace_status"] == "unavailable"
    assert result["failure_category"] != "agent_coordination_failure"
    assert result["trace"]["agent_steps"] == 0
    assert result["trace"]["handoffs"] == 0
    assert result["trace"]["missing_agents"] == []


def test_empty_trace_is_incomplete_with_coordination_failure() -> None:
    """trace_events=[] -> trace_status='incomplete' with agent_coordination_failure."""
    result = evaluate_packet("AcmeFlow", PACKET, PROBLEMS, PEOPLE, trace_events=[])

    assert result["trace_status"] == "incomplete"
    assert result["failure_category"] == "agent_coordination_failure"
    assert result["trace"]["agent_steps"] == 0
    assert result["trace"]["handoffs"] == 0
    assert result["trace"]["missing_agents"] == EXPECTED_AGENTS


def test_partial_trace_is_incomplete_with_coordination_failure() -> None:
    """Only 3 of 7 agents -> trace_status='incomplete' with coordination failure."""
    partial = [
        agent_step(
            agent=agent,
            role="writer",
            reads=[],
            writes=[],
            output_summary=f"{agent} done",
        )
        for agent in EXPECTED_AGENTS[:3]
    ]
    result = evaluate_packet("AcmeFlow", PACKET, PROBLEMS, PEOPLE, trace_events=partial)

    assert result["trace_status"] == "incomplete"
    assert result["failure_category"] == "agent_coordination_failure"
    assert result["trace"]["agent_steps"] == 3
    assert result["trace"]["handoffs"] == 0


def test_full_trace_is_complete_without_coordination_failure() -> None:
    """All 7 agents plus 6 handoffs -> trace_status='complete', no failure."""
    full = _make_full_trace()
    result = evaluate_packet("AcmeFlow", PACKET, PROBLEMS, PEOPLE, trace_events=full)

    assert result["trace_status"] == "complete"
    assert result["failure_category"] != "agent_coordination_failure"
    assert result["trace"]["agent_steps"] == 7
    assert result["trace"]["handoffs"] == 6
    assert result["trace"]["missing_agents"] == []

    coord_metric = next(m for m in result["metrics"] if m["name"] == "Agent coordination")
    assert coord_metric["score"] == 10.0


def test_full_trace_with_errored_event_is_incomplete() -> None:
    """A recorded stage error must fail coordination regardless of its score."""
    overrides = {"qa_verification": "error"}
    full = _make_full_trace(overrides=overrides)
    result = evaluate_packet("AcmeFlow", PACKET, PROBLEMS, PEOPLE, trace_events=full)

    assert result["trace"]["agent_steps"] == 7
    assert result["trace"]["handoffs"] == 6

    coord_metric = next(m for m in result["metrics"] if m["name"] == "Agent coordination")
    assert coord_metric["score"] == 7.0

    assert result["trace"]["has_errors"] is True
    assert result["trace_status"] == "incomplete"
    assert result["failure_category"] == "agent_coordination_failure"
