"""Command-line interface for local UpSearch orchestration."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path

from .config import load_settings
from .connectors import default_connector_profiles
from .harnessed_orchestrator import run_harnessed_packet, report
from .model_router import ModelRouter, TaskType
from .schemas import AgentRunRecord
from .seed_packets import build_baseten_seed_packet
from .tracking import RunLogger


DEFAULT_SEED_ROOT = Path("docs/opportunity-intelligence/oppprep-seed")


def _print_phase_one() -> None:
    print("Phase 1 lane: AI infrastructure / inference")
    print()
    print("Why this lane:")
    print("- We already validated the manual loop with Baseten.")
    print("- The company/problem/person/one-pager/outreach packet shape is concrete.")
    print("- It exercises the product's hardest parts without broadening too early.")
    print()
    print("Biggest challenges:")
    print("1. Keeping structured state clean across companies, people, problems, artifacts, and approvals.")
    print("2. Source verification and identity resolution, especially LinkedIn and role pages.")
    print("3. Cost-aware model routing so high-token research uses DeepSeek and final QA uses stronger review.")
    print("4. Logging every run to W&B without leaking secrets or private message content unnecessarily.")
    print("5. Preserving hard approval gates before any external send or schedule action.")
    print("6. Treating browser automation as a swappable connector, not a hard dependency.")
    print("7. Building harnesses so model calls are typed, validated, budgeted, and logged.")


def _print_connectors() -> None:
    print("Replaceable connector surfaces:")
    for profile in default_connector_profiles():
        capabilities = ", ".join(sorted(capability.value for capability in profile.capabilities))
        auth = "authenticated" if profile.authenticated else "auth required"
        print(f"- {profile.name} ({profile.kind.value}, {auth}): {capabilities}")
        if profile.notes:
            print(f"  {profile.notes}")


def _build_seed(args: argparse.Namespace) -> None:
    settings = load_settings()
    router = ModelRouter(settings)
    logger = RunLogger(settings)

    seed_root = Path(args.seed_root)
    if args.company.lower() != "baseten":
        raise SystemExit("Only the Baseten seed packet is wired for Phase 1 right now.")

    packet = build_baseten_seed_packet(seed_root)
    output_path = Path(args.output)
    packet.write_json(output_path)

    run_id = logger.new_run_id()
    logger.log_record(
        AgentRunRecord(
            run_id=run_id,
            agent="orchestrator",
            run_type="seed_packet_build",
            company=packet.company.name,
            lane=packet.lane,
            model_provider="deterministic",
            model_name="none",
            source_urls=[source.url for source in packet.problem.sources],
            artifact_paths=[str(output_path), *packet.technical_note.artifact_paths],
        )
    )
    logger.log_event(
        "model_routes",
        {
            task: asdict(route)
            for task, route in router.routes_for_phase_one().items()
        },
    )

    print(f"Wrote packet: {output_path}")
    print(f"Logged run: {run_id}")
    print(f"Tracking events: {logger.events_path}")
    print()
    print("Approval state: required before any external action.")
    for draft in packet.outreach_drafts:
        print(
            f"- {draft.person_name}: {draft.channel.value}, "
            f"{draft.word_count} words, {draft.approval_status.value}, {draft.external_action.value}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="UpSearch local orchestration tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("phase1", help="Print the Phase 1 lane and biggest challenges.")
    subparsers.add_parser("connectors", help="List replaceable connector surfaces.")

    build_seed = subparsers.add_parser(
        "build-seed",
        help="Build a deterministic packet from the validated Oppprep seed corpus.",
    )
    build_seed.add_argument("--company", default="baseten")
    build_seed.add_argument("--seed-root", default=str(DEFAULT_SEED_ROOT))
    build_seed.add_argument("--output", default=".upsearch/packets/baseten.json")

    run_packet = subparsers.add_parser(
        "run",
        help="Run the full harnessed packet workflow for a company (Profile → Company → Problem → People → Note → Outreach → QA → DB).",
    )
    run_packet.add_argument("--company", required=True, help="Company name, e.g. Baseten")
    run_packet.add_argument("--lane", default="ai_infra",
                            choices=["ai_infra", "inference_systems", "agentic_ai", "developer_tools", "data_platforms", "robotics_ai"])
    run_packet.add_argument("--profile", default="profile.txt", help="Path to profile text file")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "phase1":
        _print_phase_one()
        return

    if args.command == "connectors":
        _print_connectors()
        return

    if args.command == "build-seed":
        _build_seed(args)
        return

    if args.command == "run":
        profile_text = Path(args.profile).read_text(encoding="utf-8") if Path(args.profile).exists() else ""
        ctx = run_harnessed_packet(
            company_name=args.company,
            lane=args.lane,
            profile_text=profile_text,
        )
        print(report(ctx))
        return

    parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
