"""Discovery Agent — finds candidate schemes from the indexed database.

MVP: filters the seed database by state applicability. The upgrade path is
adding vector search over scheme descriptions and live crawling — the
interface (ctx.candidates out) stays the same.
"""
import json
from pathlib import Path

from backend.agents.base import BaseAgent, AgentContext

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "schemes.json"


class DiscoveryAgent(BaseAgent):
    name = "discovery"
    label = "Discovery Agent"
    emoji = "🔍"

    async def run(self, ctx: AgentContext):
        ctx.schemes = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        yield self.event(f"Searching indexed database — {len(ctx.schemes)} schemes loaded")
        await self.pause()

        state = ctx.profile.state
        ctx.candidates = [
            s for s in ctx.schemes
            if s["state"] == "ALL" or (state and s["state"] == state)
        ]
        by_cat = {}
        for s in ctx.candidates:
            by_cat.setdefault(s["category"], 0)
            by_cat[s["category"]] += 1
        cats = ", ".join(f"{v} {k}" for k, v in sorted(by_cat.items()))
        yield self.event(f"{len(ctx.candidates)} candidate schemes for your state ({cats})")
        await self.pause()
        yield self.event("Candidate list handed to Eligibility Agent", state="done")
