from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from browser_task_copilot.main import create_app


def _task_payload() -> dict:
    return {
        "intent": "Locate account ACME-448 and increase credit limit from 2000 to 3000",
        "target": {"base_url": "https://ops.internal.example", "workspace": "billing-admin"},
        "policy_profile": "high-risk",
    }


def test_approval_timeout_returns_conflict_and_fails_task() -> None:
    app = create_app()
    client = TestClient(app)

    create_resp = client.post("/api/tasks", json=_task_payload())
    assert create_resp.status_code == 200
    created = create_resp.json()
    assert created["status"] == "waiting_approval"
    task_id = created["task_id"]
    pending_action_id = created["pending_approval"]["action_id"]

    service = app.state.task_service
    task = service._store.get_task(task_id)
    assert task is not None
    task.pending_approval.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    service._store.save_task(task)

    approve_resp = client.post(
        f"/api/tasks/{task_id}/approve",
        json={
            "action_id": pending_action_id,
            "decision": "approved",
            "approved_by": {
                "email": "lead-finops@example.com",
                "role": "finops_lead",
            },
            "reason": "late approval",
        },
    )
    assert approve_resp.status_code == 409
    assert "deadline exceeded" in approve_resp.json()["detail"]

    get_resp = client.get(f"/api/tasks/{task_id}")
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["status"] == "failed"
    assert body["error_code"] == "ApprovalExpired"
