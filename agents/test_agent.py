import os
import json
import subprocess
import tempfile
from .base_agent import BaseAgent, AgentResult

SYSTEM = """You are a QA engineer. Given an API description, generate pytest test cases.
Return ONLY valid Python code (no markdown, no explanation).
The tests must use httpx.Client with base_url from the TEST_BASE_URL env var (default http://localhost:8000).
Cover: happy path, edge cases, validation errors.
Import only: pytest, httpx, os."""


class TestAgent(BaseAgent):
    name = "Test Agent"

    def run(self, context: dict) -> AgentResult:
        project_root = context.get("project_root", ".")
        existing_tests_path = os.path.join(project_root, "tests", "test_api.py")

        api_description = """
GeoExpense REST API:
- GET  /api/expenses         → list all expenses (returns array of Expense objects)
- GET  /api/expenses/summary → returns {total, tax_deductible, potential_savings, by_category, count}
- POST /api/expenses         → create expense. Body: {title, amount, vendor, latitude, longitude, city}
- DELETE /api/expenses/{id}  → delete expense by id

Expense object fields: id, title, amount, category, vendor, latitude, longitude, city, date, tax_deductible, ai_note
"""

        if self.ai_enabled:
            generated_code = self.ask(
                SYSTEM,
                f"Generate pytest tests for this API:\n{api_description}",
                max_tokens=1200,
            )
            # Strip possible markdown fences
            code = generated_code.strip()
            if code.startswith("```"):
                lines = code.split("\n")
                code = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            # Write generated tests
            os.makedirs(os.path.dirname(existing_tests_path), exist_ok=True)
            with open(existing_tests_path, "w") as f:
                f.write(code)
        elif not os.path.exists(existing_tests_path):
            return AgentResult(
                agent=self.name,
                status="warning",
                summary="Skipped test generation — no ANTHROPIC_API_KEY. No existing test file found.",
                details=["Set ANTHROPIC_API_KEY to let Claude generate tests."],
            )

        # Run them
        env = os.environ.copy()
        env["TEST_BASE_URL"] = context.get("base_url", "http://localhost:8000")
        result = subprocess.run(
            ["python", "-m", "pytest", existing_tests_path, "-v", "--tb=short", "--no-header"],
            capture_output=True, text=True, env=env, cwd=project_root, timeout=60,
        )

        output = result.stdout + result.stderr
        passed = output.count(" PASSED")
        failed = output.count(" FAILED")
        errors = output.count(" ERROR")
        total = passed + failed + errors

        status = "passed" if failed == 0 and errors == 0 and total > 0 else "failed"
        summary = f"{passed}/{total} tests passed"
        if failed > 0:
            summary += f", {failed} failed"

        details = [line for line in output.split("\n") if line.strip()][:30]

        return AgentResult(
            agent=self.name,
            status=status,
            summary=summary,
            details=details,
            artifacts={"passed": passed, "failed": failed, "total": total, "test_file": existing_tests_path},
        )
