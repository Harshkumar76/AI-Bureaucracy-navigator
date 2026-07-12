"""Shared agent plumbing.

Each agent is an async generator: it yields SSE-able event dicts as it works
and mutates the shared AgentContext. The Coordinator runs them in sequence
and streams every event to the browser, so the UI shows real progress —
not an animation of fictional work.
"""
import asyncio
from dataclasses import dataclass, field
from typing import List, Optional

from backend.models import UserProfile, Finding

# small pacing delay so streamed steps are visually followable in the UI
STEP_DELAY = 0.35


@dataclass
class AgentContext:
    profile: UserProfile
    schemes: List[dict] = field(default_factory=list)     # full seed DB
    candidates: List[dict] = field(default_factory=list)  # after Discovery
    findings: List[Finding] = field(default_factory=list) # after Eligibility
    checklist: List[dict] = field(default_factory=list)   # after Document agent
    summary: Optional[str] = None


class BaseAgent:
    name = "agent"
    label = "Agent"
    emoji = "🤖"

    def event(self, message: str, state: str = "log") -> dict:
        return {"type": "agent", "agent": self.name, "label": self.label,
                "emoji": self.emoji, "state": state, "message": message}

    async def pause(self):
        await asyncio.sleep(STEP_DELAY)

    async def run(self, ctx: AgentContext):
        raise NotImplementedError
        yield  # makes this an async generator in subclasses' eyes
