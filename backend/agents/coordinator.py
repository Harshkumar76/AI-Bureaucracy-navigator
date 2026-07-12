"""Coordinator — orchestrates the agent pipeline and streams SSE events.

Pipeline: Intake -> Discovery -> Eligibility -> Documents -> Verification,
then a final `findings` event with the full results payload.
"""
import json

from backend import llm
from backend.agents.base import AgentContext
from backend.agents.intake import IntakeAgent
from backend.agents.discovery import DiscoveryAgent
from backend.agents.eligibility import EligibilityAgent
from backend.agents.documents import DocumentAgent
from backend.agents.verification import VerificationAgent
from backend.models import UserProfile

PIPELINE = [IntakeAgent, DiscoveryAgent, EligibilityAgent, DocumentAgent, VerificationAgent]


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _fallback_summary(ctx: AgentContext) -> str:
    eligible = [f for f in ctx.findings if f.status == "eligible"]
    possible = [f for f in ctx.findings if f.status == "possible"]
    missing = sum(1 for c in ctx.checklist if not c["have"])
    parts = []
    if eligible:
        parts.append(f"You appear eligible for {len(eligible)} scheme(s), "
                     f"including {eligible[0].name}.")
    if possible:
        parts.append(f"{len(possible)} more may apply — answer the highlighted "
                     f"questions to confirm.")
    if not eligible and not possible:
        parts.append("No matches yet with the current details — try filling more "
                     "fields; many schemes depend on income, category, or occupation.")
    if missing:
        parts.append(f"Your document checklist has {missing} item(s) to arrange.")
    parts.append("Final eligibility always depends on the documents you submit — "
                 "verify on the official portal linked in each card.")
    return " ".join(parts)


async def run_pipeline(profile: UserProfile):
    ctx = AgentContext(profile=profile)
    yield _sse({"type": "start", "message": "Coordinator: launching agent pipeline"})

    for agent_cls in PIPELINE:
        agent = agent_cls()
        yield _sse({"type": "agent", "agent": agent.name, "label": agent.label,
                    "emoji": agent.emoji, "state": "start", "message": "starting..."})
        async for event in agent.run(ctx):
            yield _sse(event)

    summary = None
    if llm.available():
        summary = llm.summarize(
            ctx.profile.model_dump(exclude_none=True),
            [f.model_dump() for f in ctx.findings],
        )
    ctx.summary = summary or _fallback_summary(ctx)

    yield _sse({
        "type": "findings",
        "summary": ctx.summary,
        "findings": [f.model_dump() for f in ctx.findings],
        "checklist": ctx.checklist,
    })
