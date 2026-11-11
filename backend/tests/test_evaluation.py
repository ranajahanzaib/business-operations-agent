import json

from opsagent.db import connect, delayed_orders, seed
from opsagent.evaluation import evaluate_delayed_order_run


def test_evaluator_checks_complete_database_coverage(tmp_path):
    path = tmp_path / "evaluation.sqlite3"
    seed(path)
    with connect(path) as c:
        c.execute(
            "INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?)",
            ("run-eval", "find delayed", "applying", "ollama", "test", "now", "now", None, None),
        )
        rows = delayed_orders(c, 5, "2026-11-10T12:00:00+00:00", 100)
        expected = {r["id"] for r in rows}
        existing = {
            r["order_id"]
            for r in c.execute(
                "SELECT order_id FROM support_tickets WHERE category='delayed_delivery' AND status IN ('open','in_progress')"
            )
        }
        c.execute(
            "INSERT INTO events(run_id,kind,payload,created_at) VALUES(?,?,?,?)",
            (
                "run-eval",
                "scenario_evidence",
                json.dumps(
                    {
                        "scenario_id": "delayed_order_support",
                        "overdue_days": 5,
                        "as_of": "2026-11-10T12:00:00+00:00",
                        "order_ids": sorted(expected),
                        "preexisting_covered_ids": sorted(expected & existing),
                    }
                ),
                "now",
            ),
        )
        c.execute(
            "INSERT INTO proposals VALUES(?,?,?,?,?,?,?,?)",
            ("proposal-eval", "run-eval", 1, "[]", "hash", "approved", "now", "operator"),
        )
        for index, order_id in enumerate(sorted(expected - existing)):
            order = c.execute("SELECT customer_id FROM orders WHERE id=?", (order_id,)).fetchone()
            ticket_id = f"new-ticket-{index}"
            c.execute(
                "INSERT INTO support_tickets VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    ticket_id,
                    f"NEW-{index}",
                    order["customer_id"],
                    order_id,
                    "delayed_delivery",
                    "normal",
                    "open",
                    "Delivery follow-up",
                    "Synthetic verification test",
                    "opsagent",
                    "now",
                    "now",
                    1,
                ),
            )
            c.execute(
                "INSERT INTO execution_ledger VALUES(?,?,?,?,?,?,?)",
                (
                    f"action-{index}",
                    "proposal-eval",
                    "applied",
                    f"key-{index}",
                    ticket_id,
                    1,
                    "now",
                ),
            )
        result = evaluate_delayed_order_run(c, "run-eval", "proposal-eval")
        assert result["overall_status"] == "passed"
        assert result["expected_action_count"] == result["actual_action_count"]
        assert not result["missing_actions"]
