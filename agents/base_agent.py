import anthropic
import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    agent: str
    status: str        # "passed" | "failed" | "warning"
    summary: str
    details: list[str] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)


class BaseAgent:
    name: str = "Base Agent"
    model: str = "claude-sonnet-4-6"
    requires_ai: bool = True

    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.ai_enabled = bool(api_key)
        self.client = anthropic.Anthropic(api_key=api_key) if self.ai_enabled else None

    def ask(self, system: str, prompt: str, max_tokens: int = 1024, fallback: str = "") -> str:
        if not self.ai_enabled:
            return fallback
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def run(self, context: dict) -> AgentResult:
        raise NotImplementedError
