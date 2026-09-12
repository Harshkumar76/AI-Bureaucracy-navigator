"""
backend/agents/discovery.py

Semantic retrieval merged into your existing structural (state) filter.
EligibilityAgent downstream needs ZERO changes -- it already reads whatever
DiscoveryAgent puts in ctx.candidates.
"""
from backend.agents.base import BaseAgent, AgentContext
from backend.database import db_connection
from backend.retrieval_service import RetrievalService


class DiscoveryAgent(BaseAgent):
    name = "discovery"
    label = "Discovery Agent"
    emoji = "🔍"

    async def run(self, ctx: AgentContext):
        with db_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT data FROM schemes WHERE state = 'ALL' OR state = %s",
                (ctx.profile.state,),
            )
            ctx.schemes = [row["data"] for row in cur.fetchall()]

        yield self.event(f"Searching indexed database — {len(ctx.schemes)} schemes loaded")
        await self.pause()

        state = ctx.profile.state
        structural_candidates = [
            s for s in ctx.schemes
            if s["state"] == "ALL" or (state and s["state"] == state)
        ]

        # Semantic search NEVER narrows the candidate pool -- it only attaches a
        # relevance score used for ranking. Every structurally-eligible scheme
        # still gets evaluated, so a scheme the user qualifies for can never be
        # hidden just because their free-text phrasing didn't match it well.
        similarity_by_id: dict[str, float] = {}
        if ctx.profile.extra_info:
            with db_connection() as retrieval_conn:
                retrieval_service = RetrievalService(retrieval_conn)
                semantic_hits = retrieval_service.retrieve(ctx.profile.extra_info)
            similarity_by_id = {hit["id"]: hit["similarity"] for hit in semantic_hits}
            if similarity_by_id:
                yield self.event(
                    f"Semantic search ranked {len(similarity_by_id)} schemes by relevance to your note"
                )
                await self.pause()

        # Rank: semantically-matched schemes first (by similarity), then the
        # rest in their original order. The FULL structural set is still passed
        # through -- ranking changes ORDER, never MEMBERSHIP.
        structural_candidates.sort(
            key=lambda s: similarity_by_id.get(s["id"], -1.0),
            reverse=True,
        )
        ctx.candidates = structural_candidates

        by_cat = {}
        for s in ctx.candidates:
            by_cat.setdefault(s["category"], 0)
            by_cat[s["category"]] += 1
        cats = ", ".join(f"{v} {k}" for k, v in sorted(by_cat.items()))
        yield self.event(f"{len(ctx.candidates)} candidate schemes for your state ({cats})")
        await self.pause()
        yield self.event("Candidate list handed to Eligibility Agent", state="done")