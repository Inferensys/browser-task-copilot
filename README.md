# browser-task-copilot

FastAPI control plane for guarded browser tasks.

The repo turns operator intent into typed browser actions, evaluates each action against YAML policy, pauses on approval boundaries, and emits replay timelines for post-run inspection. The planner can run in a deterministic mode for local development and tests, or in a live Azure OpenAI mode that produces structured action plans from natural-language requests.

Current scope:

- Real planner, simulated executor.
- Policy and approval decisions are deterministic and app-owned.
- Replay artifacts are timeline records, not real browser screenshots.

## Core pieces

- `src/browser_task_copilot/planner.py`: planner contract and deterministic fallback.
- `src/browser_task_copilot/azure_planner.py`: Azure OpenAI planner that emits typed `ProposedAction` objects.
- `src/browser_task_copilot/policy.py`: YAML policy loader and rule evaluator.
- `src/browser_task_copilot/service.py`: task lifecycle, approval handling, replay emission.
- `policies/*.yaml`: allow / deny / approval rules.
- `demo/input/` and `demo/output/`: captured live examples from the Azure planner path.

## Live demo artifacts

The checked-in demo set was generated against the live Azure planner path with `gpt-5-mini`.

| Scenario | Input | Output |
| --- | --- | --- |
| Read-only account inspection | `demo/input/task-readonly.json` | `demo/output/task-readonly-create.json` |
| Policy-gated account mutation | `demo/input/task-approval.json` | `demo/output/task-approval-final.json` |
| External export denied by policy defaults | `demo/input/task-denied.json` | `demo/output/task-denied-create.json` |

Approval path excerpt:

```json
{
  "task_id": "live_mutation_001",
  "status": "succeeded",
  "actions": [
    { "action_id": "live_mutation_001_open_dashboard", "type": "navigate" },
    { "action_id": "live_mutation_001_search_account", "type": "read_dom" },
    { "action_id": "live_mutation_001_open_account", "type": "click" },
    { "action_id": "live_mutation_001_edit_spend_cap", "type": "read_dom" },
    { "action_id": "live_mutation_001_submit_update", "type": "submit_form" }
  ],
  "planner": {
    "mode": "azure",
    "provider": "azure-openai",
    "model": "gpt-5-mini",
    "confidence": 0.8
  },
  "summary": {
    "actions_total": 5,
    "actions_executed": 4,
    "approvals_used": 1
  }
}
```

Replay excerpt for the denied path:

```json
{
  "task_id": "live_external_export_001",
  "timeline": [
    {
      "action_id": "live_external_export_001_open_home",
      "decision": "deny",
      "detail": "no rule matched; using policy defaults"
    }
  ]
}
```

See `demo/output/demo-summary.json` for the full scenario matrix.

## Running locally

Install dependencies:

```bash
uv sync --extra dev
```

Start the API in deterministic mode:

```bash
uv run uvicorn browser_task_copilot.main:app --app-dir src --reload
```

Health check:

```bash
curl -s http://127.0.0.1:8000/healthz
```

## Azure planner mode

```bash
export BROWSER_TASK_COPILOT_PROVIDER=azure
export AZURE_OPENAI_ENDPOINT="https://<resource>.openai.azure.com/"
export AZURE_OPENAI_API_KEY="<key>"
export AZURE_OPENAI_API_VERSION="2025-04-01-preview"
export AZURE_OPENAI_PLANNER_DEPLOYMENT="gpt-5-mini"
uv run uvicorn browser_task_copilot.main:app --app-dir src --reload
```

Generate the checked-in demo set:

```bash
uv run python scripts/run_live_demo.py
```

Provider-specific notes live in `docs/azure-foundry.md`.

## API surface

- `POST /api/tasks`
- `GET /api/tasks/{task_id}`
- `POST /api/tasks/{task_id}/approve`
- `GET /api/tasks/{task_id}/replay`
- `POST /api/policies/evaluate`

## Example request

```bash
curl -sS http://127.0.0.1:8000/api/tasks \
  -H "content-type: application/json" \
  -d @demo/input/task-approval.json
```

If the response returns `waiting_approval`, submit the pending action:

```bash
curl -sS http://127.0.0.1:8000/api/tasks/live_mutation_001/approve \
  -H "content-type: application/json" \
  -d '{
    "action_id": "live_mutation_001_submit_update",
    "decision": "approved",
    "approved_by": {
      "user_id": "u_demo_finops_001",
      "email": "lead-finops@example.com",
      "role": "finops_lead"
    },
    "reason": "Approved for replay capture.",
    "signature": "sha256:demo-approval"
  }'
```

## Notes

- The executor is intentionally simulated; this repo focuses on plan typing, policy separation, approval flow, and replay structure.
- Policy rules are evaluated independently from model output. The planner can suggest actions, but it cannot grant itself access.
- Live planner output is normalized into `ProposedAction` objects before the policy engine sees it.

## Tests

```bash
uv run pytest -q
```
