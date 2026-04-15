from fastapi.testclient import TestClient

from browser_task_copilot.main import create_app


def _task_payload(policy_profile: str = "default") -> dict:
    return {
        "intent": "Locate account ACME-448 and increase credit limit from 2000 to 3000",
        "target": {
            "base_url": "https://ops.internal.example",
            "workspace": "billing-admin",
        },
        "context": {
            "tenant": "acme-prod",
            "requester": "ops.engineer@example.com",
            "tags": ["billing", "credit-limit"],
        },
        "constraints": {
            "max_actions": 25,
            "task_timeout_seconds": 420,
            "allow_file_downloads": False,
        },
        "policy_profile": policy_profile,
    }


def test_task_lifecycle_waits_for_approval_and_succeeds() -> None:
    client = TestClient(create_app())

    create_resp = client.post("/api/tasks", json=_task_payload("default"))
    assert create_resp.status_code == 200
    created = create_resp.json()
    assert created["status"] == "waiting_approval"
    task_id = created["task_id"]
    pending_action_id = created["pending_approval"]["action_id"]
    assert pending_action_id.endswith("_submit_change")

    approve_resp = client.post(
        f"/api/tasks/{task_id}/approve",
        json={
            "action_id": pending_action_id,
            "decision": "approved",
            "approved_by": {
                "user_id": "u_00184",
                "email": "lead-finops@example.com",
                "role": "finops_lead",
            },
            "reason": "Approved under FIN-992",
            "signature": "sha256:123",
        },
    )
    assert approve_resp.status_code == 200
    completed = approve_resp.json()
    assert completed["status"] == "succeeded"
    assert completed["summary"]["approvals_used"] == 1
    assert completed["summary"]["actions_executed"] >= 2

    replay_resp = client.get(f"/api/tasks/{task_id}/replay")
    assert replay_resp.status_code == 200
    replay = replay_resp.json()
    assert replay["task_id"] == task_id
    assert len(replay["timeline"]) >= 4
