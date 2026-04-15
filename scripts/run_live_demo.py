from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT / "demo" / "input"
OUTPUT_DIR = ROOT / "demo" / "output"


def main() -> None:
    os.environ.setdefault("BROWSER_TASK_COPILOT_PROVIDER", "azure")
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    from browser_task_copilot.main import create_app

    client = TestClient(create_app())

    requests = {
        "readonly": {
            "task_id": "live_readonly_001",
            "intent": (
                "Navigate through billing-admin to account ACME-448, inspect the overview and "
                "risk note sections, and return the current credit limit, hold flags, and last "
                "risk review note. This is read-only."
            ),
            "target": {
                "base_url": "https://ops.internal.example",
                "workspace": "billing-admin",
            },
            "context": {
                "tenant": "acme-prod",
                "requester": "ops.engineer@example.com",
                "tags": ["billing", "read-only", "demo"],
            },
            "constraints": {
                "max_actions": 6,
                "task_timeout_seconds": 420,
                "allow_file_downloads": False,
            },
            "policy_profile": "default",
        },
        "approval": {
            "task_id": "live_mutation_001",
            "intent": (
                "Locate account ACME-448 and update the account spending cap from 2000 to 3000 "
                "with reason temporary procurement exception, then submit the form."
            ),
            "target": {
                "base_url": "https://ops.internal.example",
                "workspace": "billing-admin",
            },
            "context": {
                "tenant": "acme-prod",
                "requester": "ops.engineer@example.com",
                "tags": ["billing", "threshold", "demo"],
            },
            "constraints": {
                "max_actions": 6,
                "task_timeout_seconds": 420,
                "allow_file_downloads": False,
            },
            "policy_profile": "default",
        },
        "denied": {
            "task_id": "live_external_export_001",
            "intent": (
                "Open the vendor settlement portal and export the current chargeback CSV for review."
            ),
            "target": {
                "base_url": "https://vendor-portal.example",
                "workspace": "settlements",
            },
            "context": {
                "tenant": "acme-prod",
                "requester": "ops.engineer@example.com",
                "tags": ["vendor", "export", "demo"],
            },
            "constraints": {
                "max_actions": 6,
                "task_timeout_seconds": 420,
                "allow_file_downloads": True,
            },
            "policy_profile": "default",
        },
    }

    summary = []
    for name, payload in requests.items():
        _write_json(INPUT_DIR / f"task-{name}.json", payload)

        create_response = client.post("/api/tasks", json=payload)
        create_response.raise_for_status()
        create_body = create_response.json()
        _write_json(OUTPUT_DIR / f"task-{name}-create.json", create_body)

        task_id = create_body["task_id"]
        replay_response = client.get(f"/api/tasks/{task_id}/replay")
        replay_response.raise_for_status()
        _write_json(OUTPUT_DIR / f"replay-{name}-initial.json", replay_response.json())

        summary_item = {
            "name": name,
            "task_id": task_id,
            "status": create_body["status"],
            "planner_mode": (create_body.get("planner") or {}).get("mode"),
            "planner_model": (create_body.get("planner") or {}).get("model"),
            "planner_confidence": (create_body.get("planner") or {}).get("confidence"),
            "actions": [action["type"] for action in create_body.get("actions", [])],
            "pending_action_id": (create_body.get("pending_approval") or {}).get("action_id"),
        }

        current_body = create_body
        approval_round = 0
        while current_body["status"] == "waiting_approval":
            approval_round += 1
            approval_response = client.post(
                f"/api/tasks/{task_id}/approve",
                json={
                    "action_id": current_body["pending_approval"]["action_id"],
                    "decision": "approved",
                    "approved_by": {
                        "user_id": "u_demo_finops_001",
                        "email": "lead-finops@example.com",
                        "role": "finops_lead",
                    },
                    "reason": "Approved for live demo replay.",
                    "signature": "sha256:demo-approval",
                },
            )
            approval_response.raise_for_status()
            current_body = approval_response.json()
            _write_json(OUTPUT_DIR / f"approve-{name}-{approval_round:02d}.json", current_body)

        if approval_round:
            final_task_response = client.get(f"/api/tasks/{task_id}")
            final_task_response.raise_for_status()
            _write_json(OUTPUT_DIR / f"task-{name}-final.json", final_task_response.json())

            final_replay_response = client.get(f"/api/tasks/{task_id}/replay")
            final_replay_response.raise_for_status()
            _write_json(OUTPUT_DIR / f"replay-{name}-final.json", final_replay_response.json())

            summary_item["approval_rounds"] = approval_round
            summary_item["final_status"] = final_task_response.json()["status"]
        else:
            summary_item["final_status"] = create_body["status"]

        summary.append(summary_item)

    _write_json(OUTPUT_DIR / "demo-summary.json", summary)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
