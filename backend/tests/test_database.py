import sqlite3

from opsagent.db import connect, delayed_orders, initialize, seed


def test_seed_counts_and_strict_delay_boundary(tmp_path):
    path = tmp_path / "business.sqlite3"
    seed(path)
    with connect(path) as c:
        assert c.execute("SELECT count(*) FROM customers").fetchone()[0] == 60
        assert c.execute("SELECT count(*) FROM orders").fetchone()[0] == 180
        assert c.execute("SELECT count(*) FROM order_items").fetchone()[0] == 360
        rows = delayed_orders(c, 5, "2026-11-10T12:00:00+00:00", 500)
        assert rows
        assert all(row["overdue_days"] > 5 for row in rows)
        assert all(row["status"] not in {"delivered", "cancelled"} for row in rows)


def test_delivered_and_cancelled_orders_never_currently_delayed(tmp_path):
    path = tmp_path / "business.sqlite3"
    seed(path)
    with connect(path) as c:
        rows = delayed_orders(c, 0, "2026-11-10T12:00:00+00:00", 500)
        assert all(row["status"] not in ("delivered", "cancelled") for row in rows)


def test_exactly_five_days_is_not_more_than_five(tmp_path):
    path = tmp_path / "business.sqlite3"
    seed(path)
    with connect(path) as c:
        c.execute(
            "UPDATE orders SET promised_delivery_date='2026-11-05T12:00:00+00:00' WHERE id='o0001'"
        )
        rows = delayed_orders(c, 5, "2026-11-10T12:00:00+00:00", 500)
        assert "o0001" not in {row["id"] for row in rows}


def test_inventory_constraints_reject_negative_values(tmp_path):
    path = tmp_path / "business.sqlite3"
    initialize(path)
    with connect(path) as c:
        try:
            c.execute("INSERT INTO inventory VALUES('x','X','Bad',-1,0,1,1,'2026-01-01',1)")
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("negative stock must violate the database invariant")
