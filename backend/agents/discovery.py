"""Discovery Agent — finds candidate schemes from the indexed database.

MVP: filters the seed database by state applicability. The upgrade path is
adding vector search over scheme descriptions and live crawling — the
interface (ctx.candidates out) stays the same.
"""
from backend.agents.base import BaseAgent, AgentContext
from backend.database import db_connection


class DiscoveryAgent(BaseAgent):
    name = "discovery"
    label = "Discovery Agent"
    emoji = "🔍"

    async def run(self, ctx: AgentContext):
        with db_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT data FROM schemes WHERE state = 'ALL' OR state = %s", (ctx.profile.state,))
            ctx.schemes = [row["data"] for row in cur.fetchall()]
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
