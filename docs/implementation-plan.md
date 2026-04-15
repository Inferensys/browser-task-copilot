# Implementation Plan: Guarded Browser Task Control Plane

## Objective

Implement a runnable control-plane service for guarded browser-task orchestration with:

- deterministic policy evaluation from YAML profiles
- in-memory task lifecycle and approval gating
- simulated action execution and replay artifact timeline
- contract-first API aligned with repository examples

## Scope for First Working Slice

### Runtime and Packaging

- Python 3.9-compatible package layout using `src/`
- dependency and tooling setup in `pyproject.toml`
- FastAPI app entrypoint for local execution via `uv`

### Domain Models

- typed task request/state models
- typed policy document models and evaluation response models
- typed approval request models with role and expiry checks
- typed replay models for timeline artifacts
- typed terminal result summary/artifact models

### Control Plane Components

- `PolicyLoader`: load and validate YAML policy profiles
- `PolicyEngine`: first-match-wins decision evaluation
- `InMemoryTaskStore`: thread-safe task and replay persistence
- `TaskService`: task lifecycle orchestration and approval handling
- `SimulatedRunner`: deterministic non-browser execution path

### Task Lifecycle for v1

1. `POST /api/tasks` creates task and action plan.
2. Service evaluates each proposed action against policy.
3. `allow` actions are simulated and recorded in replay.
4. `require_approval` pauses task with pending deadline.
5. `POST /api/tasks/{id}/approve` resumes or denies action.
6. Approval expiration transitions task to `failed` with `ApprovalExpired`.
7. Terminal state includes summary metrics and replay pointers.

### API Surface

- `POST /api/tasks`
- `GET /api/tasks/{id}`
- `POST /api/tasks/{id}/approve`
- `GET /api/tasks/{id}/replay`
- `POST /api/policies/evaluate`

### Testing Strategy

- policy evaluation: allow/deny/require_approval path coverage
- approval timeout: pending action expires and task fails
- lifecycle: create -> wait -> approve -> wait -> approve -> success

## Non-Goals in v1

- real Playwright/browser runtime
- distributed persistence or job queue
- cryptographic signature verification for approvals

## Upgrade Path

v1 keeps interfaces stable for future runtime replacement:

- swap simulated runner with real browser executor
- replace in-memory store with persistent backend
- add async worker execution and retry orchestration
