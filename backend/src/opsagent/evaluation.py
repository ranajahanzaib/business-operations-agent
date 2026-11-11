"""Deterministic evaluation against committed business state."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

from .db import delayed_orders


def evaluate_delayed_order_run(c: sqlite3.Connection, run_id: str, proposal_id: str | None) -> dict:
    evidence_row = c.execute(
        "SELECT payload FROM events WHERE run_id=? AND kind='scenario_evidence' ORDER BY id DESC LIMIT 1",
        (run_id,),
    ).fetchone()
    if not evidence_row:
        return {
            "evaluation_id": str(uuid4()),
            "run_id": run_id,
            "scenario_id": "delayed_order_support",
            "expected_action_count": None,
            "actual_action_count": 0,
            "missing_actions": [],
            "unexpected_actions": [],
            "duplicate_actions": [],
            "violated_invariants": [],
            "checks_passed": [],
            "checks_failed": [],
            "overall_status": "inconclusive",
        }
    evidence = json.loads(evidence_row[0])
    model_expected = set(evidence["order_ids"])
    previous = set(evidence["preexisting_covered_ids"])
    as_of = evidence["as_of"]
    overdue_days = evidence["overdue_days"]
    live_rows = delayed_orders(c, overdue_days, as_of, 501)
    if len(live_rows) > 500:
        return {
            "evaluation_id": str(uuid4()),
            "run_id": run_id,
            "scenario_id": "delayed_order_support",
            "expected_action_count": None,
            "actual_action_count": 0,
            "missing_actions": [],
            "unexpected_actions": [],
            "duplicate_actions": [],
            "violated_invariants": ["evaluation_result_limit_exceeded"],
            "checks_passed": [],
            "checks_failed": ["complete_independent_query"],
            "overall_status": "inconclusive",
        }
    expected = {row["id"] for row in live_rows}
    expected_actions = len(expected - previous)
    if evidence.get("truncated"):
        return {
            "evaluation_id": str(uuid4()),
            "run_id": run_id,
            "scenario_id": "delayed_order_support",
            "expected_action_count": expected_actions,
            "actual_action_count": 0,
            "missing_actions": [],
            "unexpected_actions": [],
            "duplicate_actions": [],
            "violated_invariants": ["source_tool_result_was_truncated"],
            "checks_passed": [],
            "checks_failed": ["complete_source_dataset"],
            "overall_status": "inconclusive",
        }
    action_rows = (
        c.execute(
            "SELECT action_id,result_reference FROM execution_ledger WHERE proposal_id=?",
            (proposal_id,),
        ).fetchall()
        if proposal_id
        else []
    )
    created_ids = {r["result_reference"] for r in action_rows}
    created_orders = set()
    if created_ids:
        marks = ",".join("?" for _ in created_ids)
        created_orders = {
            r["order_id"]
            for r in c.execute(
                f"SELECT order_id FROM support_tickets WHERE id IN ({marks})", tuple(created_ids)
            )
        }
    unexpected = sorted(created_orders - expected)
    missing = []
    duplicates = []
    relationship_errors = []
    for order_id in sorted(expected):
        matches = c.execute(
            "SELECT id,customer_id,order_id FROM support_tickets WHERE order_id=? AND category='delayed_delivery' AND status IN ('open','in_progress')",
            (order_id,),
        ).fetchall()
        if not matches:
            missing.append(order_id)
        if len(matches) > 1:
            duplicates.append(order_id)
        order = c.execute("SELECT customer_id FROM orders WHERE id=?", (order_id,)).fetchone()
        if order and any(
            ticket["customer_id"] != order["customer_id"] or ticket["order_id"] != order_id
            for ticket in matches
        ):
            relationship_errors.append(order_id)
    approved = (
        c.execute("SELECT status,actor FROM proposals WHERE id=?", (proposal_id,)).fetchone()
        if proposal_id
        else None
    )
    unauthorized = expected_actions > 0 and (
        not approved or approved["status"] != "approved" or not approved["actor"]
    )
    passed = []
    failed = []
    for label, condition in [
        ("model_order_selection_matches_database", model_expected == expected),
        ("all_expected_orders_have_active_tickets", not missing),
        ("no_duplicate_active_tickets", not duplicates),
        ("no_unexpected_ticket_actions", not unexpected),
        ("ticket_customer_order_links_match", not relationship_errors),
        ("writes_have_operator_approval", not unauthorized),
        ("action_count_matches_expected", len(action_rows) == expected_actions),
    ]:
        (passed if condition else failed).append(label)
    return {
        "evaluation_id": str(uuid4()),
        "run_id": run_id,
        "scenario_id": "delayed_order_support",
        "expected_action_count": expected_actions,
        "actual_action_count": len(action_rows),
        "missing_actions": missing,
        "unexpected_actions": unexpected,
        "duplicate_actions": duplicates,
        "violated_invariants": relationship_errors
        + (["write_without_operator_approval"] if unauthorized else []),
        "checks_passed": passed,
        "checks_failed": failed,
        "overall_status": "passed" if not failed else "failed",
        "evaluated_at": datetime.now(UTC).isoformat(),
    }


def store_evaluation(c: sqlite3.Connection, run_id: str, result: dict, mode: str = "live") -> None:
    c.execute(
        "INSERT INTO evaluations VALUES(?,?,?,?,?,?,?)",
        (
            result["evaluation_id"],
            run_id,
            result["scenario_id"],
            mode,
            result["overall_status"],
            json.dumps(result, sort_keys=True),
            datetime.now(UTC).isoformat(),
        ),
    )


def evaluate_proposal_actions(
    c: sqlite3.Connection, run_id: str, proposal_id: str, actions: list[dict]
) -> dict:
    row = c.execute(
        "SELECT payload FROM events WHERE run_id=? AND kind='scenario_evidence' ORDER BY id DESC LIMIT 1",
        (run_id,),
    ).fetchone()
    scenario = json.loads(row[0]).get("scenario_id", "business_write") if row else "business_write"
    if scenario == "delayed_order_support":
        return evaluate_delayed_order_run(c, run_id, proposal_id)
    expected = {a["action_id"] for a in actions}
    ledger = {
        r["action_id"]: r["result_reference"]
        for r in c.execute(
            "SELECT action_id,result_reference FROM execution_ledger WHERE proposal_id=?",
            (proposal_id,),
        )
    }
    missing = []
    unexpected = sorted(set(ledger) - expected)
    invalid = []
    for action in actions:
        reference = ledger.get(action["action_id"])
        if not reference:
            missing.append(action["action_id"])
            continue
        kind = action.get("action_type", "create_support_ticket")
        if kind == "create_support_ticket":
            record = c.execute(
                "SELECT customer_id,order_id,category,priority,status FROM support_tickets WHERE id=?",
                (reference,),
            ).fetchone()
            if (
                not record
                or record["customer_id"] != action["customer_id"]
                or record["order_id"] != action.get("order_id")
                or record["category"] != action["category"]
                or record["status"] != "open"
            ):
                invalid.append(action["action_id"])
        elif kind == "reserve_inventory":
            record = c.execute(
                "SELECT order_id,sku,quantity,status FROM inventory_reservations WHERE id=?",
                (reference,),
            ).fetchone()
            if (
                not record
                or record["order_id"] != action["order_id"]
                or record["sku"] != action["sku"]
                or record["quantity"] != action["quantity"]
                or record["status"] != "reserved"
            ):
                invalid.append(action["action_id"])
        elif kind == "update_ticket_priority":
            record = c.execute(
                "SELECT priority,version,status FROM support_tickets WHERE id=?", (reference,)
            ).fetchone()
            if (
                not record
                or record["priority"] != action["new_priority"]
                or record["version"] != action["expected_version"] + 1
                or record["status"] not in {"open", "in_progress"}
            ):
                invalid.append(action["action_id"])
        else:
            invalid.append(action["action_id"])
    approval = c.execute("SELECT status,actor FROM proposals WHERE id=?", (proposal_id,)).fetchone()
    authorized = bool(approval and approval["status"] == "approved" and approval["actor"])
    failed = []
    passed = []
    checks = [
        ("all_approved_actions_applied", not missing),
        ("no_unexpected_ledger_actions", not unexpected),
        ("business_rows_match_approved_payload", not invalid),
        ("operator_approval_recorded", authorized),
    ]
    for label, ok in checks:
        (passed if ok else failed).append(label)
    return {
        "evaluation_id": str(uuid4()),
        "run_id": run_id,
        "scenario_id": scenario,
        "expected_action_count": len(expected),
        "actual_action_count": len(ledger),
        "missing_actions": missing,
        "unexpected_actions": unexpected,
        "duplicate_actions": [],
        "violated_invariants": invalid
        + (["write_without_operator_approval"] if not authorized else []),
        "checks_passed": passed,
        "checks_failed": failed,
        "overall_status": "passed" if not failed else "failed",
        "evaluated_at": datetime.now(UTC).isoformat(),
    }
