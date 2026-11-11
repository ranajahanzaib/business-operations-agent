import asyncio
import hashlib
import json
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from opsagent import api
from opsagent.db import connect, seed


def setup_proposal(path, monkeypatch):
    seed(path)
    monkeypatch.setattr(api, "connect", lambda: connect(path))
    action = {
        "action_id": "stable-action-1",
        "customer_id": "c005",
        "customer_name": "Customer 05",
        "order_id": "o0005",
        "order_number": "NS-000005",
        "category": "delayed_delivery",
        "priority": "normal",
        "status": "open",
        "subject": "Delivery update",
        "description": "Synthetic approved ticket",
        "reason": "Order is overdue.",
    }
    payload = json.dumps([action], sort_keys=True, separators=(",", ":"))
    with connect(path) as c:
        c.execute("UPDATE orders SET status='delivered' WHERE id!='o0005'")
        c.execute(
            "UPDATE orders SET status='shipped',promised_delivery_date='2026-10-01T12:00:00+00:00' WHERE id='o0005'"
        )
        c.execute(
            "INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?)",
            (
                "run-1",
                "test request",
                "awaiting_approval",
                "ollama",
                "test-model",
                datetime.now(UTC).isoformat(),
                datetime.now(UTC).isoformat(),
                None,
                None,
            ),
        )
        c.execute(
            "INSERT INTO proposals VALUES(?,?,?,?,?,?,?,NULL)",
            (
                "proposal-1",
                "run-1",
                1,
                payload,
                hashlib.sha256(payload.encode()).hexdigest(),
                "pending",
                datetime.now(UTC).isoformat(),
            ),
        )
        c.execute(
            "INSERT INTO events(run_id,kind,payload,created_at) VALUES(?,?,?,?)",
            (
                "run-1",
                "scenario_evidence",
                json.dumps(
                    {
                        "scenario_id": "delayed_order_support",
                        "overdue_days": 5,
                        "as_of": "2026-11-10T12:00:00+00:00",
                        "order_ids": ["o0005"],
                        "preexisting_covered_ids": [],
                    }
                ),
                datetime.now(UTC).isoformat(),
            ),
        )

    async def no_checkpoint_resume(_run_id, _approved):
        return None

    from opsagent import workflow

    monkeypatch.setattr(workflow, "resume", no_checkpoint_resume)


def test_approval_commits_and_verifies_exact_proposal(tmp_path, monkeypatch):
    path = tmp_path / "business.sqlite3"
    setup_proposal(path, monkeypatch)
    result = asyncio.run(api.approve("proposal-1", {"id": "operator", "role": "operator"}))
    assert result["status"] == "completed"
    assert result["verification"]["overall_status"] == "passed"
    with connect(path) as c:
        assert (
            c.execute(
                "SELECT count(*) FROM support_tickets WHERE order_id='o0005' AND status='open'"
            ).fetchone()[0]
            == 1
        )
        assert (
            c.execute(
                "SELECT count(*) FROM execution_ledger WHERE action_id='stable-action-1'"
            ).fetchone()[0]
            == 1
        )


def test_proposal_does_not_create_business_ticket_before_approval(tmp_path, monkeypatch):
    path = tmp_path / "business.sqlite3"
    setup_proposal(path, monkeypatch)
    with connect(path) as c:
        assert (
            c.execute(
                "SELECT count(*) FROM support_tickets WHERE order_id='o0005' AND status='open'"
            ).fetchone()[0]
            == 0
        )
        assert (
            c.execute("SELECT status FROM proposals WHERE id='proposal-1'").fetchone()[0]
            == "pending"
        )


def test_rejection_preserves_business_state(tmp_path, monkeypatch):
    path = tmp_path / "business.sqlite3"
    setup_proposal(path, monkeypatch)
    result = asyncio.run(api.reject("proposal-1", {"id": "operator", "role": "operator"}))
    assert result["status"] == "rejected"
    with connect(path) as c:
        assert (
            c.execute(
                "SELECT count(*) FROM support_tickets WHERE order_id='o0005' AND status='open'"
            ).fetchone()[0]
            == 0
        )
        assert (
            c.execute("SELECT status FROM proposals WHERE id='proposal-1'").fetchone()[0]
            == "rejected"
        )


def test_appearing_duplicate_rolls_back_approval(tmp_path, monkeypatch):
    path = tmp_path / "business.sqlite3"
    setup_proposal(path, monkeypatch)
    with connect(path) as c:
        c.execute("UPDATE support_tickets SET status='open' WHERE order_id='o0005'")
    with pytest.raises(HTTPException) as error:
        asyncio.run(api.approve("proposal-1", {"id": "operator", "role": "operator"}))
    assert error.value.status_code == 409
    with connect(path) as c:
        assert (
            c.execute("SELECT status FROM proposals WHERE id='proposal-1'").fetchone()[0]
            == "pending"
        )
        assert c.execute("SELECT count(*) FROM execution_ledger").fetchone()[0] == 0
