import os
import glob
import json
from .base_agent import BaseAgent, AgentResult

SYSTEM = """You are a senior software engineer performing a code review.
Analyze the provided code files and return a JSON object with:
{
  "overall": "passed" | "warning" | "failed",
  "score": 0-100,
  "issues": [{"severity": "error"|"warning"|"info", "file": "...", "message": "..."}],
  "strengths": ["..."],
  "summary": "one paragraph summary"
}
Be specific. Focus on: security, correctness, maintainability, API best practices."""


class CodeReviewAgent(BaseAgent):
    name = "Code Review Agent"

    def run(self, context: dict) -> AgentResult:
        project_root = context.get("project_root", ".")
        patterns = ["**/*.py", "**/*.js"]
        files_content = {}

        for pattern in patterns:
            for path in glob.glob(os.path.join(project_root, pattern), recursive=True):
                rel = os.path.relpath(path, project_root)
                if any(skip in rel for skip in ["__pycache__", "node_modules", ".git", "venv"]):
                    continue
                try:
                    with open(path) as f:
                        content = f.read()
                    if content.strip():
                        files_content[rel] = content[:3000]  # cap per file
                except Exception:
                    pass

        if not files_content:
            return AgentResult(agent=self.name, status="failed", summary="No source files found.")

        if not self.ai_enabled:
            return AgentResult(
                agent=self.name,
                status="warning",
                summary=f"Skipped — no ANTHROPIC_API_KEY set. Found {len(files_content)} files to review.",
                details=[f"[SKIP] {path}" for path in files_content],
            )

        file_block = "\n\n".join(
            f"=== {path} ===\n{content}" for path, content in list(files_content.items())[:10]
        )

        raw = self.ask(
            SYSTEM,
            f"Review these files:\n\n{file_block}",
            max_tokens=1500,
        )

        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            data = json.loads(raw[start:end])
            issues = data.get("issues", [])
            errors = [i for i in issues if i["severity"] == "error"]
            warnings = [i for i in issues if i["severity"] == "warning"]

            details = [f"Score: {data.get('score', 'N/A')}/100"]
            details += [f"[ERROR] {i['file']}: {i['message']}" for i in errors]
            details += [f"[WARN]  {i['file']}: {i['message']}" for i in warnings]
            details += [f"[OK]    {s}" for s in data.get("strengths", [])]

            return AgentResult(
                agent=self.name,
                status=data.get("overall", "warning"),
                summary=data.get("summary", raw[:200]),
                details=details,
                artifacts={"score": data.get("score"), "issue_count": len(issues)},
            )
        except Exception:
            return AgentResult(
                agent=self.name,
                status="warning",
                summary=raw[:300],
                details=[raw],
            )
