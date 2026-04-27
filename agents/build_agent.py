import os
import subprocess
import sys
import importlib.util
from .base_agent import BaseAgent, AgentResult


class BuildAgent(BaseAgent):
    name = "Build Agent"

    def run(self, context: dict) -> AgentResult:
        project_root = context.get("project_root", ".")
        details = []
        issues = []

        # 1. Check requirements.txt exists
        req_path = os.path.join(project_root, "requirements.txt")
        if os.path.exists(req_path):
            details.append("[OK] requirements.txt found")
        else:
            issues.append("requirements.txt missing")

        # 2. Check critical packages are importable
        required = ["fastapi", "uvicorn", "sqlalchemy", "anthropic", "httpx"]
        for pkg in required:
            spec = importlib.util.find_spec(pkg.replace("-", "_"))
            if spec:
                details.append(f"[OK] {pkg} installed")
            else:
                issues.append(f"Package not installed: {pkg}")
                details.append(f"[FAIL] {pkg} not found")

        # 3. Check source files exist
        critical_files = [
            "app/backend/main.py",
            "app/backend/database.py",
            "app/frontend/index.html",
            "app/frontend/app.js",
            "agents/code_review_agent.py",
            "agents/test_agent.py",
            "agents/build_agent.py",
            "agents/deploy_agent.py",
            "pipeline.py",
        ]
        for rel in critical_files:
            full = os.path.join(project_root, rel)
            if os.path.exists(full):
                details.append(f"[OK] {rel}")
            else:
                issues.append(f"Missing file: {rel}")
                details.append(f"[FAIL] {rel} not found")

        # 4. Syntax-check Python files
        py_files = ["app/backend/main.py", "app/backend/database.py", "pipeline.py"]
        for rel in py_files:
            full = os.path.join(project_root, rel)
            if os.path.exists(full):
                result = subprocess.run(
                    [sys.executable, "-m", "py_compile", full],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    details.append(f"[OK] {rel} syntax valid")
                else:
                    issues.append(f"Syntax error in {rel}: {result.stderr.strip()}")
                    details.append(f"[FAIL] {rel} syntax error")

        # 5. Ask Claude for a build health assessment (optional — skipped if no API key)
        issue_summary = "\n".join(issues) if issues else "None"
        default_assessment = "All checks passed." if not issues else f"{len(issues)} issue(s) need attention."
        assessment = self.ask(
            "You are a DevOps engineer. Given a build checklist result, provide a 1-2 sentence assessment "
            "of build health and the most important action to take if anything is wrong. Be concise.",
            f"Build issues found:\n{issue_summary}\n\nChecks passed: {len(details) - len(issues)}/{len(details)}",
            max_tokens=200,
            fallback=default_assessment,
        )

        status = "failed" if any("FAIL" in d for d in details) else "passed"
        summary = f"{len(details) - len(issues)}/{len(details)} checks passed. {assessment}"

        return AgentResult(
            agent=self.name,
            status=status,
            summary=summary,
            details=details,
            artifacts={"issues": issues, "checks_passed": len(details) - len(issues)},
        )
