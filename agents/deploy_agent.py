import os
import json
import subprocess
import sys
import signal
import time
import socket
from .base_agent import BaseAgent, AgentResult

DEPLOY_LOG = "deploy_log.json"


def find_free_port(start=8000, end=8020) -> int:
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) != 0:
                return port
    return start


class DeployAgent(BaseAgent):
    name = "Deploy Agent"

    def run(self, context: dict) -> AgentResult:
        project_root = context.get("project_root", ".")
        details = []

        # 1. Determine port
        port = find_free_port()
        details.append(f"[OK] Selected port: {port}")

        # 2. Start the server as a subprocess
        backend_dir = os.path.join(project_root, "app", "backend")
        cmd = [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", f"--port={port}"]

        env = os.environ.copy()
        env["PYTHONPATH"] = backend_dir

        proc = subprocess.Popen(
            cmd,
            cwd=backend_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        details.append(f"[OK] Server process started (PID {proc.pid})")

        # 3. Wait for it to be ready
        ready = False
        for _ in range(20):
            time.sleep(0.5)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("localhost", port)) == 0:
                    ready = True
                    break

        if not ready:
            proc.terminate()
            stderr = proc.stderr.read().decode()[:500]
            return AgentResult(
                agent=self.name,
                status="failed",
                summary="Server failed to start within 10 seconds.",
                details=details + [f"Stderr: {stderr}"],
            )

        details.append(f"[OK] Server is live at http://localhost:{port}")

        # 4. Quick smoke test
        import httpx
        try:
            r = httpx.get(f"http://localhost:{port}/api/expenses/summary", timeout=5)
            r.raise_for_status()
            summary = r.json()
            details.append(f"[OK] Health check passed — {summary.get('count', 0)} expenses loaded")
        except Exception as e:
            details.append(f"[WARN] Health check failed: {e}")

        # 5. Write deploy log
        deploy_record = {
            "url": f"http://localhost:{port}",
            "pid": proc.pid,
            "port": port,
            "status": "running",
        }
        log_path = os.path.join(project_root, DEPLOY_LOG)
        with open(log_path, "w") as f:
            json.dump(deploy_record, f, indent=2)
        details.append(f"[OK] Deploy log written to {DEPLOY_LOG}")

        # 6. Ask Claude for a deployment summary (optional — skipped if no API key)
        summary_text = self.ask(
            "You are a DevOps engineer. Write one sentence confirming a successful deployment, "
            "mentioning the URL and what the app does. Be brief and professional.",
            f"App: GeoExpense (AI-powered business expense tracker with map visualization)\n"
            f"URL: http://localhost:{port}\nStatus: running\nExpenses in DB: {summary.get('count', 0)}",
            max_tokens=100,
            fallback=f"GeoExpense deployed successfully at http://localhost:{port}.",
        )

        return AgentResult(
            agent=self.name,
            status="passed",
            summary=summary_text,
            details=details,
            artifacts=deploy_record,
        )
