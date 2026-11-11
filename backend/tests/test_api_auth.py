from fastapi.testclient import TestClient

from opsagent import api, db


def test_read_only_actor_is_denied_approval(tmp_path, monkeypatch):
    path = tmp_path / "business.sqlite3"
    db.seed(path)
    monkeypatch.setattr(api, "connect", lambda: db.connect(path))
    monkeypatch.setattr(api, "initialize", lambda: db.initialize(path))
    with db.connect(path) as c:
        c.execute(
            "INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?)",
            (
                "auth-run",
                "test request",
                "awaiting_approval",
                "ollama",
                "model",
                "now",
                "now",
                None,
                None,
            ),
        )
        c.execute(
            "INSERT INTO proposals VALUES(?,?,?,?,?,?,?,NULL)",
            ("auth-proposal", "auth-run", 1, "[]", "invalid", "pending", "now"),
        )
    with TestClient(api.app) as client:
        response = client.post(
            "/api/proposals/auth-proposal/approve",
            headers={"Authorization": "Bearer local-auditor-token"},
        )
    assert response.status_code == 403


def test_public_config_exposes_bounded_runtime_settings(monkeypatch):
    monkeypatch.setattr(api, "initialize", lambda: None)
    monkeypatch.setenv("OPSAGENT_MAX_ITERATIONS", "7")
    body = api.public_config()
    assert body["runtime"]["max_iterations"] == 7
    assert body["runtime"]["num_ctx"] == 8192

    monkeypatch.setenv("OPSAGENT_MAX_ITERATIONS", "0")
    from fastapi.testclient import TestClient

    with TestClient(api.app) as client:
        response = client.get("/api/config/public")
    assert response.status_code == 500
    assert "OPSAGENT_MAX_ITERATIONS" in response.json()["detail"]


def test_model_tool_calls_are_schema_validated_and_normalized():
    normalized, error = api.validate_model_tool_calls(
        {
            "tool_calls": [
                {
                    "function": {
                        "name": "get_order",
                        "arguments": '{"order_id":"o0001"}',
                    }
                }
            ]
        }
    )
    assert error is None
    assert normalized[0]["function"]["arguments"] == {"order_id": "o0001"}

    invalid, error = api.validate_model_tool_calls(
        {
            "tool_calls": [
                {
                    "function": {
                        "name": "list_delayed_orders",
                        "arguments": {"overdue_days": "five"},
                    }
                }
            ]
        }
    )
    assert invalid is None
    assert "missing required fields" in error


def test_event_stream_resumes_after_last_event_id(tmp_path, monkeypatch):
    path = tmp_path / "business.sqlite3"
    db.seed(path)
    monkeypatch.setattr(api, "connect", lambda: db.connect(path))
    monkeypatch.setattr(api, "initialize", lambda: db.initialize(path))
    with db.connect(path) as c:
        c.execute(
            "INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?)",
            ("stream-run", "test", "completed", "fixture", "fixture", "now", "now", None, None),
        )
        db.log_event(c, "stream-run", "first", {"value": 1})
        db.log_event(c, "stream-run", "second", {"value": 2})

    with TestClient(api.app) as client:
        response = client.get(
            "/api/runs/stream-run/stream",
            headers={"Authorization": "Bearer local-operator-token", "Last-Event-ID": "1"},
        )
        assert response.status_code == 200
        assert "event: second" in response.text
        assert "event: first" not in response.text
        assert "id: 2" in response.text

        invalid = client.get(
            "/api/runs/stream-run/stream",
            headers={"Authorization": "Bearer local-operator-token", "Last-Event-ID": "-1"},
        )
        assert invalid.status_code == 400


def test_business_detail_endpoints_include_linked_records(tmp_path, monkeypatch):
    path = tmp_path / "business.sqlite3"
    db.seed(path)
    monkeypatch.setattr(api, "connect", lambda: db.connect(path))
    monkeypatch.setattr(api, "initialize", lambda: db.initialize(path))
    headers = {"Authorization": "Bearer local-operator-token"}

    with TestClient(api.app) as client:
        customer = client.get("/api/customers/c001", headers=headers)
        order = client.get("/api/orders/o0001", headers=headers)
        inventory = client.get("/api/inventory/p001", headers=headers)
        ticket = client.get("/api/tickets/t0001", headers=headers)

    assert (
        customer.status_code
        == order.status_code
        == inventory.status_code
        == ticket.status_code
        == 200
    )
    assert customer.json()["orders"]
    assert order.json()["customer"]["id"] == "c001"
    assert "items" in order.json() and "tickets" in order.json()
    assert inventory.json()["sku"] == "NS-0001"
    assert ticket.json()["order"]["id"] == "o0001"


def test_business_data_supports_filtered_server_pagination_and_sort(tmp_path, monkeypatch):
    path = tmp_path / "business.sqlite3"
    db.seed(path)
    monkeypatch.setattr(api, "connect", lambda: db.connect(path))
    monkeypatch.setattr(api, "initialize", lambda: db.initialize(path))
    with TestClient(api.app) as client:
        response = client.get(
            "/api/data/orders",
            params={"limit": 10, "offset": 10, "search": "NS-000", "sort_by": "order_number"},
            headers={"Authorization": "Bearer local-operator-token"},
        )
    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 180
    assert body["offset"] == 10
    assert len(body["items"]) == 10
    assert body["items"][0]["order_number"] == "NS-000011"


def test_trace_sanitizer_redacts_credentials_and_emails():
    assert api._sanitize_trace_value(
        {"email": "person@example.test", "nested": {"token": "secret", "name": "synthetic"}}
    ) == {"email": "[redacted]", "nested": {"token": "[redacted]", "name": "synthetic"}}


def test_operator_revision_supersedes_proposal_and_creates_fresh_run(tmp_path, monkeypatch):
    path = tmp_path / "business.sqlite3"
    db.seed(path)
    monkeypatch.setattr(api, "connect", lambda: db.connect(path))
    monkeypatch.setattr(api, "initialize", lambda: db.initialize(path))
    from opsagent import workflow

    async def no_op(*_args):
        return None

    monkeypatch.setattr(workflow, "resume", no_op)
    monkeypatch.setattr(workflow, "start", no_op)
    with db.connect(path) as c:
        c.execute(
            "INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?)",
            (
                "revision-run",
                "Inspect delayed orders",
                "awaiting_approval",
                "fixture",
                "m",
                "now",
                "now",
                None,
                None,
            ),
        )
        c.execute(
            "INSERT INTO proposals VALUES(?,?,?,?,?,?,?,NULL)",
            ("revision-proposal", "revision-run", 1, "[]", "hash", "pending", "now"),
        )

    with TestClient(api.app) as client:
        auditor = client.post(
            "/api/proposals/revision-proposal/revise",
            headers={"Authorization": "Bearer local-auditor-token"},
            json={"message": "Change the requested ticket priority"},
        )
        assert auditor.status_code == 403
        revised = client.post(
            "/api/proposals/revision-proposal/revise",
            headers={"Authorization": "Bearer local-operator-token"},
            json={"message": "Use urgent priority and explain the reason"},
        )
        assert revised.status_code == 202
        new_run_id = revised.json()["new_run_id"]
        duplicate = client.post(
            "/api/proposals/revision-proposal/revise",
            headers={"Authorization": "Bearer local-operator-token"},
            json={"message": "Try revising it a second time"},
        )
        assert duplicate.status_code == 409

    with db.connect(path) as c:
        assert (
            c.execute("SELECT status FROM proposals WHERE id='revision-proposal'").fetchone()[0]
            == "superseded"
        )
        assert (
            c.execute("SELECT status FROM runs WHERE id='revision-run'").fetchone()[0]
            == "replanned"
        )
        new_run = c.execute("SELECT request,status FROM runs WHERE id=?", (new_run_id,)).fetchone()
        assert new_run["status"] == "pending"
        assert "Use urgent priority" in new_run["request"]
