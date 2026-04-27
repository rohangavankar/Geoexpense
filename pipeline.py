#!/usr/bin/env python3
"""
GeoExpense AI Pipeline
Orchestrates four AI agents to review, test, build, and deploy the application.
"""

import os
import sys
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

sys.path.insert(0, os.path.dirname(__file__))
from agents.code_review_agent import CodeReviewAgent
from agents.test_agent import TestAgent
from agents.build_agent import BuildAgent
from agents.deploy_agent import DeployAgent

console = Console()
PROJECT_ROOT = os.path.dirname(__file__)

STATUS_ICONS = {
    "passed": "[bold green]✓ PASSED[/bold green]",
    "warning": "[bold yellow]⚠ WARNING[/bold yellow]",
    "failed": "[bold red]✗ FAILED[/bold red]",
}

AGENT_DESCRIPTIONS = {
    "Code Review Agent": "Claude analyzes all source files for quality, security, and best practices",
    "Test Agent":        "Claude generates pytest test cases, then runs them against the API",
    "Build Agent":       "Validates dependencies, file structure, and Python syntax",
    "Deploy Agent":      "Starts the FastAPI server and runs a live health check",
}


def run_pipeline(skip_deploy: bool = False) -> dict:
    console.print(Panel.fit(
        "[bold cyan]GeoExpense AI Pipeline[/bold cyan]\n"
        "[dim]Powered by Claude — Code Review → Test → Build → Deploy[/dim]",
        border_style="cyan",
    ))

    agents = [
        CodeReviewAgent(),
        TestAgent(),
        BuildAgent(),
    ]
    if not skip_deploy:
        agents.append(DeployAgent())

    results = []
    context = {"project_root": PROJECT_ROOT, "base_url": "http://localhost:8000"}

    for agent in agents:
        desc = AGENT_DESCRIPTIONS.get(agent.name, "")
        console.print(f"\n[bold white]▶ {agent.name}[/bold white]")
        console.print(f"  [dim]{desc}[/dim]")

        start = time.time()
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task(f"  Running {agent.name}...", total=None)
            try:
                result = agent.run(context)
            except Exception as e:
                from agents.base_agent import AgentResult
                result = AgentResult(
                    agent=agent.name,
                    status="failed",
                    summary=f"Agent crashed: {e}",
                    details=[str(e)],
                )

        elapsed = time.time() - start
        results.append(result)

        # Update context for downstream agents (deploy needs server info)
        if result.artifacts.get("port"):
            context["base_url"] = f"http://localhost:{result.artifacts['port']}"

        icon = STATUS_ICONS.get(result.status, result.status)
        console.print(f"  {icon} [dim]({elapsed:.1f}s)[/dim]")
        console.print(f"  [italic]{result.summary[:200]}[/italic]")

        if result.details:
            for line in result.details[:8]:
                color = "red" if "[FAIL]" in line else "yellow" if "[WARN]" in line else "dim"
                console.print(f"    [{color}]{line}[/{color}]")
            if len(result.details) > 8:
                console.print(f"    [dim]... and {len(result.details) - 8} more[/dim]")

        # Stop pipeline if build fails
        if result.status == "failed" and agent.name == "Build Agent":
            console.print("\n[bold red]Pipeline halted — fix build errors before deploying.[/bold red]")
            break

    # Final summary table
    console.print("\n")
    table = Table(title="Pipeline Summary", box=box.ROUNDED, border_style="cyan")
    table.add_column("Agent", style="bold white")
    table.add_column("Status", justify="center")
    table.add_column("Key Metric")

    for r in results:
        icon = STATUS_ICONS.get(r.status, r.status)
        metric = ""
        if r.artifacts.get("score"):
            metric = f"Score: {r.artifacts['score']}/100"
        elif r.artifacts.get("total"):
            metric = f"Tests: {r.artifacts['passed']}/{r.artifacts['total']} passed"
        elif r.artifacts.get("checks_passed") is not None:
            metric = f"Checks: {r.artifacts['checks_passed']} passed"
        elif r.artifacts.get("url"):
            metric = r.artifacts["url"]
        table.add_row(r.agent, icon, metric)

    console.print(table)

    passed = sum(1 for r in results if r.status == "passed")
    total = len(results)
    overall = "passed" if passed == total else "warning" if passed >= total // 2 else "failed"

    if overall == "passed":
        console.print(Panel(
            f"[bold green]All {total} agents passed![/bold green]\n"
            f"[green]App is live at: {context.get('base_url')}[/green]",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"[yellow]{passed}/{total} agents passed — review issues above.[/yellow]",
            border_style="yellow",
        ))

    return {"results": results, "overall": overall, "url": context.get("base_url")}


if __name__ == "__main__":
    skip_deploy = "--no-deploy" in sys.argv
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print(Panel(
            "[yellow]No ANTHROPIC_API_KEY set — running in limited mode.[/yellow]\n"
            "[dim]Code Review will be skipped. Tests will run from existing file. "
            "Build and Deploy will run without AI commentary.\n"
            "Set ANTHROPIC_API_KEY to enable all AI features.[/dim]",
            border_style="yellow",
            title="Limited Mode",
        ))
    run_pipeline(skip_deploy=skip_deploy)
