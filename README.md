# browser-task-copilot

FastAPI control plane for guarded browser task execution.  
v1 uses a simulated runner (no real browser runtime) and focuses on policy gating, approval flow, lifecycle transitions, and replay artifact emission.

## Current implementation

- Policy evaluation from YAML profiles in `policies/*.yaml` (`first-match-wins`).
- Typed models for tasks, approvals, policy requests, replay events, and terminal results.
- In-memory task store and deterministic task state machine.
- Simulated execution engine that produces replay timeline and artifact URIs.
- Approval TTL enforcement and role-based approval checks.

## Project layout

- `src/browser_task_copilot/main.py`: FastAPI app and endpoints
- `src/browser_task_copilot/models.py`: typed domain/API models
- `src/browser_task_copilot/policy.py`: policy loader and rule evaluator
- `src/browser_task_copilot/service.py`: task orchestration and state machine
- `src/browser_task_copilot/store.py`: in-memory persistence layer
- `tests/`: policy, approval timeout, and lifecycle tests
- `docs/implementation-plan.md`: execution plan for this implementation

## Run locally (`uv` + Python 3.9)

```bash
uv sync --extra dev
uv run uvicorn browser_task_copilot.main:app --app-dir src --reload
```

Health check:

```bash
curl -s http://127.0.0.1:8000/healthz
```

## API surface

- `POST /api/tasks`
- `GET /api/tasks/{task_id}`
- `POST /api/tasks/{task_id}/approve`
- `GET /api/tasks/{task_id}/replay`
- `POST /api/policies/evaluate`

## Example flow

Create a task:

```bash
curl -sS http://127.0.0.1:8000/api/tasks \
  -H "content-type: application/json" \
  -d @examples/task-create.json
```

If status is `waiting_approval`, approve the pending action:

```bash
curl -sS http://127.0.0.1:8000/api/tasks/<task_id>/approve \
  -H "content-type: application/json" \
  -d @examples/approval-event.json
```

Fetch task and replay:

```bash
curl -sS http://127.0.0.1:8000/api/tasks/<task_id>
curl -sS http://127.0.0.1:8000/api/tasks/<task_id>/replay
```

## Policy notes

Profiles:

- `default-policy.yaml`: allows internal navigation/read actions, gates writes.
- `high-risk-policy.yaml`: tighter profile, requires approval for click/input.

Supported decisions:

- `allow`
- `deny`
- `require_approval`

## Tests

```bash
uv run pytest
```

Covered:

- policy decision paths
- approval timeout handling
- end-to-end lifecycle: create -> wait -> approve -> succeed
