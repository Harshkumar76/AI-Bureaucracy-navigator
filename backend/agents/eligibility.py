"""Eligibility Agent — runs every candidate through the deterministic rule engine.

The engine (rules.py) returns eligible / possible / ineligible with
human-readable reasons and the exact profile fields that would resolve
each 'possible'. No LLM involvement — results are consistent and explainable.
"""
from backend.agents.base import BaseAgent, AgentContext
from backend.models import Finding
from backend.rules import evaluate


class EligibilityAgent(BaseAgent):
    name = "eligibility"
    label = "Eligibility Agent"
    emoji = "⚖️"

    async def run(self, ctx: AgentContext):
        yield self.event(f"Checking {len(ctx.candidates)} schemes against your profile...")
        await self.pause()

        counts = {"eligible": 0, "possible": 0, "ineligible": 0}
        for scheme in ctx.candidates:
            status, reasons, unknowns = evaluate(ctx.profile, scheme["rules"])
            counts[status] += 1
            have = set(d.lower() for d in ctx.profile.documents_have)
            missing = [d for d in scheme["documents"] if d.lower() not in have]
            ctx.findings.append(Finding(
                scheme_id=scheme["id"],
                name=scheme["name"],
                benefit=scheme["benefit"],
                status=status,
                reasons=reasons,
                unknown_fields=unknowns,
                documents=scheme["documents"],
                documents_missing=missing,
                official_url=scheme["official_url"],
                apply_mode=scheme["apply_mode"],
                last_verified=scheme["last_verified"],
            ))

        order = {"eligible": 0, "possible": 1, "ineligible": 2}
        ctx.findings.sort(key=lambda f: order[f.status])

        yield self.event(
            f"Verdict: {counts['eligible']} eligible ✅, {counts['possible']} possibly eligible ❓, "
            f"{counts['ineligible']} not eligible ❌"
        )
        await self.pause()
        yield self.event("Every verdict carries its reasons — nothing is a black box", state="done")
