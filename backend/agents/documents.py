"""Document Agent — builds the consolidated document checklist.

Aggregates required documents across eligible/possible schemes, dedupes,
and marks what the user already has (from the form's checkboxes).
Upgrade path: DigiLocker issued-documents integration to auto-verify.
"""
from backend.agents.base import BaseAgent, AgentContext


class DocumentAgent(BaseAgent):
    name = "documents"
    label = "Document Agent"
    emoji = "📄"

    async def run(self, ctx: AgentContext):
        relevant = [f for f in ctx.findings if f.status in ("eligible", "possible")]
        yield self.event(f"Building document checklist for {len(relevant)} relevant schemes...")
        await self.pause()

        have = set(d.lower() for d in ctx.profile.documents_have)
        needed = {}  # doc -> [scheme names]
        for f in relevant:
            for doc in f.documents:
                needed.setdefault(doc, []).append(f.name)

        ctx.checklist = [
            {"document": doc, "have": doc.lower() in have, "needed_for": schemes}
            for doc, schemes in sorted(needed.items(), key=lambda kv: -len(kv[1]))
        ]
        missing = [c for c in ctx.checklist if not c["have"]]
        if missing:
            top = ", ".join(c["document"] for c in missing[:3])
            yield self.event(f"{len(missing)} documents to arrange — most needed: {top}")
        else:
            yield self.event("You already have every document these schemes require 🎉")
        await self.pause()
        yield self.event("Checklist ready", state="done")
