"""
W&B Tracker — logs every pipeline run as a W&B experiment.
Each outreach attempt is one run. Supervisor scores are included when available.
"""
import os
import wandb
from upsearch.sourcing.base import Post


def log(
    post: Post,
    analysis: dict,
    strategy: dict,
    draft: str,
    sent: bool = False,
    supervisor_summary: dict | None = None,
) -> str:
    agent_scores = supervisor_summary.get("agent_scores", {}) if supervisor_summary else {}
    overall_score = supervisor_summary.get("overall_score") if supervisor_summary else None

    run = wandb.init(
        project="upsearch",
        name=f"{post.source} | {post.title[:40]}",
        tags=[
            post.source,
            analysis.get("contact_type", "unknown"),
            f"fit-{analysis.get('fit_score', 0)}",
        ],
        config={
            # Lead metadata
            "source": post.source,
            "subreddit": post.subreddit,
            "post_url": post.url,
            "contact_type": analysis.get("contact_type", ""),
            "target_role": strategy.get("target_role", ""),
            "channel": strategy.get("channel", "email"),
            # Outreach status
            "sent": sent,
            "reply": False,
            # Supervisor scores
            "supervisor_overall": overall_score,
            "supervisor_scout": agent_scores.get("scout"),
            "supervisor_analyst": agent_scores.get("analyst"),
            "supervisor_strategist": agent_scores.get("strategist"),
            "supervisor_writer": agent_scores.get("writer"),
            "supervisor_flags": supervisor_summary.get("total_flags", 0) if supervisor_summary else 0,
        },
    )

    # Log scalar metrics (visible in W&B charts)
    metrics = {
        "fit_score": analysis.get("fit_score", 0),
        "word_count": len(draft.split()),
        "sent": int(sent),
    }
    if overall_score is not None:
        metrics["supervisor_overall_score"] = overall_score
        for agent, score in agent_scores.items():
            if score is not None:
                metrics[f"supervisor_{agent}_score"] = score

    wandb.log(metrics)

    # Save draft + full analysis as an artifact
    artifact = wandb.Artifact(
        name="outreach",
        type="email_draft",
        description=f"Draft for: {post.title[:60]}",
    )
    with artifact.new_file("draft.txt", mode="w") as f:
        f.write(f"Source: {post.url}\n")
        f.write(f"Problem: {analysis.get('problem', '')}\n")
        f.write(f"Hook: {strategy.get('hook', '')}\n\n")
        f.write("--- DRAFT ---\n\n")
        f.write(draft)

    if supervisor_summary:
        with artifact.new_file("supervisor_report.json", mode="w") as f:
            import json
            json.dump(supervisor_summary, f, indent=2)

    run.log_artifact(artifact)

    run_id = run.id
    wandb.finish()
    return run_id
