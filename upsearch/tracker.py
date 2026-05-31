"""
W&B Tracker — logs every pipeline run as a W&B experiment.
Each outreach attempt is one run. Reply/sent status can be updated later.
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
) -> str:
    run = wandb.init(
        project="upsearch",
        name=f"{post.source} | {post.title[:40]}",
        tags=[post.source, analysis.get("contact_type", "unknown")],
        config={
            "source": post.source,
            "subreddit": post.subreddit,
            "post_url": post.url,
            "fit_score": analysis.get("fit_score", 0),
            "contact_type": analysis.get("contact_type", ""),
            "target_role": strategy.get("target_role", ""),
            "channel": strategy.get("channel", "email"),
            "sent": sent,
            "reply": False,
        },
    )

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

    run.log_artifact(artifact)
    wandb.log({
        "fit_score": analysis.get("fit_score", 0),
        "word_count": len(draft.split()),
        "sent": int(sent),
    })

    run_id = run.id
    wandb.finish()
    return run_id
