"""Seed packet builders based on the manually validated Oppprep corpus."""

from __future__ import annotations

from pathlib import Path

from .schemas import (
    Company,
    OpportunityPacket,
    OutreachChannel,
    OutreachDraft,
    Person,
    Problem,
    Source,
    SourceType,
    TechnicalNote,
)


def _read_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def build_baseten_seed_packet(seed_root: Path) -> OpportunityPacket:
    """Build the first validated Phase 1 packet without external actions."""

    note_path = seed_root / "baseten-adapter-aware-routing-note.md"
    send_packet_path = seed_root / "baseten-first-send-packet.md"
    one_pager_path = seed_root / "one-pagers" / "baseten-one-pager.gdocs.docx"

    common_sources = [
        Source(
            url="https://www.baseten.co/blog/powering-inference-for-the-continual-learning-era/",
            title="Powering inference for the continual learning era",
            source_type=SourceType.COMPANY_BLOG,
        ),
        Source(
            url="https://www.baseten.co/blog/introducing-the-baseten-loops-sdk/",
            title="Introducing the Baseten Loops SDK",
            source_type=SourceType.COMPANY_BLOG,
        ),
        Source(
            url="https://docs.vllm.ai/en/stable/features/lora/",
            title="vLLM LoRA documentation",
            source_type=SourceType.DOCS,
        ),
        Source(
            url="https://github.com/predibase/lorax",
            title="LoRAX repository",
            source_type=SourceType.GITHUB,
        ),
    ]

    company = Company(
        name="Baseten",
        lane="AI infrastructure / inference",
        website="https://www.baseten.co/",
        careers_url="https://www.baseten.co/resources/careers/",
        fit_score=0.93,
        sponsorship_signal="Visible prior H-1B signal in third-party employer records; verify per role.",
        sources=[
            Source(
                url="https://www.baseten.co/resources/careers/",
                title="Baseten careers",
                source_type=SourceType.CAREERS,
            ),
            *common_sources[:2],
        ],
    )

    problem = Problem(
        company_name="Baseten",
        title="Adapter-aware routing for continual-learning inference",
        summary=(
            "Baseten's continual-learning work reframes new checkpoints and LoRA adapters as "
            "candidate hypotheses rather than silent replacements. The serving layer needs "
            "routing, compatibility validation, provenance, telemetry, and promotion rules."
        ),
        buildable_angle=(
            "Build an adapter-aware routing and validation service with an adapter registry, "
            "deterministic traffic splits, compatibility gates, provenance logs, and promotion reports."
        ),
        success_criteria=[
            "Every request records base model, adapter version, route, experiment, latency, and status.",
            "Candidate adapters are blocked until compatibility and smoke checks pass.",
            "Promotion reports compare candidate and control behavior before rollout.",
        ],
        sources=common_sources,
    )

    people = [
        Person(
            name="Bola Malek",
            company_name="Baseten",
            role="Product / Forward Deployed Engineering surface",
            relevance_reason=(
                "Closest first target because she is publicly tied to Baseten's continual-learning "
                "and Frontier Gateway work."
            ),
            best_channel=OutreachChannel.LINKEDIN_CONNECTION,
            profile_urls=["https://www.linkedin.com/in/bolamalek/"],
            sources=[
                Source(
                    url="https://www.baseten.co/author/bola-malek/",
                    title="Baseten author page: Bola Malek",
                    source_type=SourceType.COMPANY_BLOG,
                )
            ],
        ),
        Person(
            name="Raymond Cano",
            company_name="Baseten",
            role="Software Engineer",
            relevance_reason=(
                "Strong fit for the Loops and checkpoint-to-deployment part of the problem."
            ),
            best_channel=OutreachChannel.LINKEDIN_CONNECTION,
            profile_urls=["https://www.linkedin.com/in/raymond-cano-57500986/"],
            sources=[
                Source(
                    url="https://www.baseten.co/author/raymond-cano/",
                    title="Baseten author page: Raymond Cano",
                    source_type=SourceType.COMPANY_BLOG,
                )
            ],
        ),
        Person(
            name="Joey Zwicker",
            company_name="Baseten",
            role="Head of Forward Deployed Engineering",
            relevance_reason=(
                "Useful FDE leadership target for routing the note to the right inference or FDE person."
            ),
            best_channel=OutreachChannel.LINKEDIN_CONNECTION,
            profile_urls=[],
            sources=[
                Source(
                    url="https://www.baseten.co/blog/joey-zwicker-joins-baseten-as-head-of-fde/",
                    title="Joey Zwicker joins Baseten as Head of FDE",
                    source_type=SourceType.COMPANY_BLOG,
                )
            ],
        ),
    ]

    technical_note = TechnicalNote(
        title="Adapter-Aware Routing for Continual-Learning Inference",
        company_name="Baseten",
        problem_title=problem.title,
        body_markdown=_read_if_exists(note_path),
        artifact_paths=[str(path) for path in [note_path, one_pager_path] if path.exists()],
        sources=[
            *common_sources,
            Source(
                url=str(note_path),
                title="Local Baseten technical note",
                source_type=SourceType.LOCAL_ARTIFACT,
            ),
        ],
    )

    outreach_drafts = [
        OutreachDraft(
            person_name="Bola Malek",
            company_name="Baseten",
            channel=OutreachChannel.LINKEDIN_CONNECTION,
            body=(
                "Hi Bola, I am a student studying inference systems for models that keep changing "
                "after deployment. Your Baseten post on continual learning made me write a short "
                "note on adapter-aware routing. Would love to connect and learn if I am framing "
                "the problem correctly."
            ),
            follow_up_days=7,
        ),
        OutreachDraft(
            person_name="Raymond Cano",
            company_name="Baseten",
            channel=OutreachChannel.LINKEDIN_CONNECTION,
            body=(
                "Hi Raymond, I am a student studying how training systems connect back into "
                "production inference. Your Baseten Loops post made me think about checkpoint "
                "deploys as routing and evaluation problems. Would love to connect and ask one "
                "technical question."
            ),
            follow_up_days=7,
        ),
        OutreachDraft(
            person_name="Joey Zwicker",
            company_name="Baseten",
            channel=OutreachChannel.LINKEDIN_CONNECTION,
            body=(
                "Hi Joey, I am a student exploring FDE-style work around production AI "
                "infrastructure. I wrote a short Baseten-specific note on adapter-aware routing "
                "for continual-learning inference and would value a pointer to the right FDE or "
                "inference person to critique it."
            ),
            follow_up_days=7,
        ),
    ]

    send_packet = _read_if_exists(send_packet_path)
    if "Status: first outreach sent" in send_packet:
        # Preserve the historical record without marking future drafts as sent.
        pass

    return OpportunityPacket(
        lane="AI infrastructure / inference",
        company=company,
        problem=problem,
        people=people,
        technical_note=technical_note,
        outreach_drafts=outreach_drafts,
    )
