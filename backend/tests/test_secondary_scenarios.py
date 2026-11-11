import asyncio
import hashlib
import json
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from opsagent import api, workflow
from opsagent.db import connect, seed


def make_run(path, run_id):
    with connect(path) as c:
        now = datetime.now(UTC).isoformat()
        c.execute(
            "INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?)",
            (
                run_id,
                "scenario test",
                "awaiting_approval",
                "ollama",
                "scripted",
                now,
                now,
                None,
                None,
            ),
        )


def make_proposal(path, run_id, actions):
    payload = json.dumps(actions, sort_keys=True, separators=(",", ":"))
    now = datetime.now(UTC).isoformat()
    proposal_id = f"proposal-{run_id}"
    with connect(path) as c:
        c.execute(
            "INSERT INTO proposals VALUES(?,?,?,?,?,?,?,NULL)",
            (
                proposal_id,
                run_id,
                1,
                payload,
                hashlib.sha256(payload.encode()).hexdigest(),
                "pending",
                now,
            ),
        )
    return proposal_id


def patch_services(path, monkeypatch):
    monkeypatch.setattr(api, "connect", lambda: connect(path))

    async def resume(_run_id, _approved):
        return None

    monkeypatch.setattr(workflow, "resume", resume)


def test_inventory_reservation_is_approved_transactional_and_idempotent(tmp_path, monkeypatch):
    path = tmp_path / "inventory.sqlite3"
    seed(path)
    patch_services(path, monkeypatch)
    run_id = "inventory-run"
    make_run(path, run_id)
    with connect(path) as c:
        order_id = None
        for row in c.execute(
            "SELECT id FROM orders WHERE status IN ('pending','processing') ORDER BY id"
        ):
            lines = c.execute(
                "SELECT sku,product_id,SUM(quantity) quantity FROM order_items WHERE order_id=? GROUP BY sku,product_id",
                (row["id"],),
            ).fetchall()
            if lines and all(
                (
                    lambda stock, line: (
                        stock
                        and stock["available_quantity"] - stock["reserved_quantity"]
                        >= line["quantity"]
                    )
                )(
                    c.execute(
                        "SELECT * FROM inventory WHERE id=?", (line["product_id"],)
                    ).fetchone(),
                    line,
                )
                for line in lines
            ):
                order_id = row["id"]
                break
        assert order_id
        before = {
            r["id"]: r["reserved_quantity"]
            for r in c.execute("SELECT id,reserved_quantity FROM inventory")
        }
    actions, _ = api.prepare_actions(
        run_id, "propose_inventory_reservation", {"order_id": order_id}
    )
    assert actions
    proposal_id = make_proposal(path, run_id, actions)
    with connect(path) as c:
        assert c.execute("SELECT count(*) FROM inventory_reservations").fetchone()[0] == 0
    result = asyncio.run(api.approve(proposal_id, {"id": "operator", "role": "operator"}))
    assert result["status"] == "completed"
    with connect(path) as c:
        assert c.execute(
            "SELECT count(*) FROM inventory_reservations WHERE order_id=? AND status='reserved'",
            (order_id,),
        ).fetchone()[0] == len(actions)
        assert any(
            r["reserved_quantity"] > before[r["id"]]
            for r in c.execute("SELECT id,reserved_quantity FROM inventory")
        )
    with pytest.raises(HTTPException) as error:
        asyncio.run(api.approve(proposal_id, {"id": "operator", "role": "operator"}))
    assert error.value.status_code == 409


def test_stale_ticket_version_rejects_escalation_without_write(tmp_path, monkeypatch):
    path = tmp_path / "escalation.sqlite3"
    seed(path)
    patch_services(path, monkeypatch)
    run_id = "escalation-run"
    make_run(path, run_id)
    with connect(path) as c:
        ticket = c.execute(
            "SELECT t.id FROM support_tickets t JOIN orders o ON o.id=t.order_id WHERE t.category='delayed_delivery' AND t.priority='high' AND t.status='open' AND o.status IN ('pending','processing','shipped') ORDER BY t.id LIMIT 1"
        ).fetchone()
        assert ticket
    actions, _ = api.prepare_actions(
        run_id,
        "propose_ticket_priority_update",
        {
            "ticket_id": ticket["id"],
            "new_priority": "urgent",
            "reason": "Delayed delivery complaint needs escalation.",
        },
    )
    assert len(actions) == 1
    proposal_id = make_proposal(path, run_id, actions)
    with connect(path) as c:
        c.execute("UPDATE support_tickets SET version=version+1 WHERE id=?", (ticket["id"],))
    with pytest.raises(HTTPException) as error:
        asyncio.run(api.approve(proposal_id, {"id": "operator", "role": "operator"}))
    assert error.value.status_code == 409
    with connect(path) as c:
        row = c.execute(
            "SELECT priority FROM support_tickets WHERE id=?", (ticket["id"],)
        ).fetchone()
        assert row["priority"] == "high"


def test_inventory_batch_rolls_back_prior_line_on_partial_conflict(tmp_path, monkeypatch):
    path = tmp_path / "atomic.sqlite3"
    seed(path)
    patch_services(path, monkeypatch)
    run_id = "atomic-run"
    make_run(path, run_id)
    with connect(path) as c:
        order_id = None
        for row in c.execute(
            "SELECT id FROM orders WHERE status IN ('pending','processing') ORDER BY id"
        ):
            lines = c.execute(
                "SELECT sku,product_id,SUM(quantity) quantity FROM order_items WHERE order_id=? GROUP BY sku,product_id",
                (row["id"],),
            ).fetchall()
            if len(lines) > 1 and all(
                (
                    lambda stock, line: (
                        stock
                        and stock["available_quantity"] - stock["reserved_quantity"]
                        >= line["quantity"]
                    )
                )(
                    c.execute(
                        "SELECT * FROM inventory WHERE id=?", (line["product_id"],)
                    ).fetchone(),
                    line,
                )
                for line in lines
            ):
                order_id = row["id"]
                break
    assert order_id
    actions, _ = api.prepare_actions(
        run_id, "propose_inventory_reservation", {"order_id": order_id}
    )
    assert len(actions) > 1
    proposal_id = make_proposal(path, run_id, actions)
    with connect(path) as c:
        first = actions[0]
        last = actions[-1]
        before = c.execute(
            "SELECT reserved_quantity FROM inventory WHERE id=?", (first["inventory_id"],)
        ).fetchone()[0]
        c.execute("UPDATE inventory SET version=version+1 WHERE id=?", (last["inventory_id"],))
    with pytest.raises(HTTPException) as error:
        asyncio.run(api.approve(proposal_id, {"id": "operator", "role": "operator"}))
    assert error.value.status_code == 409
    with connect(path) as c:
        assert (
            c.execute(
                "SELECT reserved_quantity FROM inventory WHERE id=?", (first["inventory_id"],)
            ).fetchone()[0]
            == before
        )
        assert c.execute("SELECT count(*) FROM inventory_reservations").fetchone()[0] == 0
        assert c.execute("SELECT count(*) FROM execution_ledger").fetchone()[0] == 0
