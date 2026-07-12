"""Intake Agent — builds the structured profile.

The form gives us clean structured fields. If the user typed anything in the
optional free-text box, we mine it for extra facts with the LLM (when
configured) and merge them in — form values always win over extracted ones.
"""
from backend import llm
from backend.agents.base import BaseAgent, AgentContext


class IntakeAgent(BaseAgent):
    name = "intake"
    label = "Intake Agent"
    emoji = "📝"

    async def run(self, ctx: AgentContext):
        p = ctx.profile
        filled = [k for k, v in p.model_dump().items()
                  if v not in (None, [], "") and k != "extra_info"]
        yield self.event(f"Structured profile received — {len(filled)} fields filled")
        await self.pause()

        text = (p.extra_info or "").strip()
        if text:
            if llm.available():
                yield self.event("Reading your additional note with the language model...")
                facts = llm.extract_facts(text)
                merged = []
                for key, value in facts.items():
                    # form values win; only fill gaps
                    if hasattr(p, key) and getattr(p, key) in (None, []):
                        try:
                            setattr(p, key, value)
                            merged.append(key)
                        except Exception:
                            pass
                if merged:
                    yield self.event(f"Learned from your note: {', '.join(merged)}")
                else:
                    yield self.event("Note read — no new structured facts found")
            else:
                yield self.event("Note saved (set LLM_API_KEY to enable automatic fact extraction)")
        await self.pause()
        yield self.event("Profile ready", state="done")
