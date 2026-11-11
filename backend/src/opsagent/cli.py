"""OpsAgent developer CLI."""

import json
import os
import sys

import httpx
import typer
import uvicorn

from .db import initialize, seed

app = typer.Typer(help="OpsAgent local business workflow reference system")


@app.command()
def init():
    initialize()
    typer.echo("Business database initialized.")


@app.command(name="seed")
def seed_demo():
    seed()
    typer.echo("Synthetic Northstar Commerce data ready.")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000):
    uvicorn.run("opsagent.api:app", host=host, port=port, reload=False)


@app.command()
def doctor():
    from pathlib import Path

    from .db import DB_PATH, connect

    initialize()
    typer.echo(f"Python: {sys.version.split()[0]}")
    typer.echo(f"SQLite: available ({Path(DB_PATH).resolve()})")
    with connect() as c:
        violations = c.execute("PRAGMA foreign_key_check").fetchall()
        typer.echo(
            f"Database integrity: {'ok' if not violations else 'foreign-key violations found'}"
        )
    provider = os.getenv("OPSAGENT_PROVIDER", "ollama")
    model = os.getenv("OPSAGENT_MODEL", "qwen3:4b-instruct")
    typer.echo(f"Provider configuration: {provider} / {model}")
    try:
        if provider == "ollama":
            response = httpx.get(
                os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/tags",
                timeout=3,
            )
            names = {x.get("name") for x in response.json().get("models", [])}
            typer.echo(
                f"Ollama: available; configured model {'present' if model in names else 'missing (run ollama pull ' + model + ')'}"
            )
        else:
            base = os.getenv("OPENAI_COMPATIBLE_BASE_URL", "http://127.0.0.1:1234/v1").rstrip("/")
            headers = (
                {"Authorization": f"Bearer {os.environ['OPENAI_COMPATIBLE_API_KEY']}"}
                if os.getenv("OPENAI_COMPATIBLE_API_KEY")
                else {}
            )
            response = httpx.get(base + "/models", headers=headers, timeout=3)
            names = {x.get("id") for x in response.json().get("data", [])}
            typer.echo(
                f"OpenAI-compatible endpoint: available; configured model {'present' if model in names else 'missing from /models'}"
            )
    except Exception as exc:
        typer.echo(
            f"Provider: unavailable ({exc}); start the configured local model server and verify its URL/model"
        )


@app.command()
def run(request: str):
    response = httpx.post(
        "http://127.0.0.1:8000/api/runs",
        json={"request": request},
        headers={
            "Authorization": f"Bearer {os.getenv('OPSAGENT_OPERATOR_TOKEN', 'local-operator-token')}"
        },
        timeout=180,
    )
    response.raise_for_status()
    typer.echo(json.dumps(response.json(), indent=2))


@app.command()
def runs():
    response = httpx.get(
        "http://127.0.0.1:8000/api/runs",
        headers={
            "Authorization": f"Bearer {os.getenv('OPSAGENT_OPERATOR_TOKEN', 'local-operator-token')}"
        },
        timeout=10,
    )
    response.raise_for_status()
    typer.echo(json.dumps(response.json(), indent=2))


@app.command()
def inspect(run_id: str):
    response = httpx.get(
        f"http://127.0.0.1:8000/api/runs/{run_id}",
        headers={
            "Authorization": f"Bearer {os.getenv('OPSAGENT_OPERATOR_TOKEN', 'local-operator-token')}"
        },
        timeout=10,
    )
    response.raise_for_status()
    typer.echo(json.dumps(response.json(), indent=2))


@app.command()
def trace(run_id: str):
    response = httpx.get(
        f"http://127.0.0.1:8000/api/runs/{run_id}/trace",
        headers={
            "Authorization": f"Bearer {os.getenv('OPSAGENT_OPERATOR_TOKEN', 'local-operator-token')}"
        },
        timeout=10,
    )
    response.raise_for_status()
    typer.echo(json.dumps(response.json(), indent=2))


@app.command()
def approve(proposal_id: str):
    response = httpx.post(
        f"http://127.0.0.1:8000/api/proposals/{proposal_id}/approve",
        headers={
            "Authorization": f"Bearer {os.getenv('OPSAGENT_OPERATOR_TOKEN', 'local-operator-token')}"
        },
        timeout=30,
    )
    response.raise_for_status()
    typer.echo(json.dumps(response.json(), indent=2))


@app.command()
def reject(proposal_id: str):
    response = httpx.post(
        f"http://127.0.0.1:8000/api/proposals/{proposal_id}/reject",
        headers={
            "Authorization": f"Bearer {os.getenv('OPSAGENT_OPERATOR_TOKEN', 'local-operator-token')}"
        },
        timeout=30,
    )
    response.raise_for_status()
    typer.echo(json.dumps(response.json(), indent=2))


@app.command()
def evaluate(run_id: str | None = None):
    headers = {
        "Authorization": f"Bearer {os.getenv('OPSAGENT_OPERATOR_TOKEN', 'local-operator-token')}"
    }
    if run_id is None:
        response = httpx.get("http://127.0.0.1:8000/api/runs", headers=headers, timeout=10)
        response.raise_for_status()
        items = response.json().get("items", [])
        if not items:
            raise typer.BadParameter("No runs are available to evaluate")
        run_id = items[0]["id"]
    response = httpx.post(
        "http://127.0.0.1:8000/api/evaluations/run",
        params={"run_id": run_id},
        headers=headers,
        timeout=20,
    )
    response.raise_for_status()
    typer.echo(json.dumps(response.json(), indent=2))


@app.command()
def reset_demo(confirmed: bool = False):
    if not confirmed:
        raise typer.BadParameter("pass --confirmed to reset synthetic data")
    from .db import connect

    with connect() as c:
        for t in [
            "execution_ledger",
            "inventory_reservations",
            "proposals",
            "evaluations",
            "events",
            "runs",
            "support_tickets",
            "order_items",
            "orders",
            "inventory",
            "customers",
        ]:
            c.execute(f"DELETE FROM {t}")
    seed()
    typer.echo("Synthetic data reset.")
