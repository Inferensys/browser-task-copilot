# browser-task-copilot

Reference repository for building browser-executing agents with explicit safety boundaries, approval gates, replay artifacts, and deterministic policy evaluation.

This repo focuses on control-plane and contract design. It is intentionally implementation-agnostic so the same contracts can back a local Playwright runner, a remote browser pool, or a VM-isolated computer-use runtime.

## Repository map

- `docs/architecture.md`: component and data-flow model
- `docs/policy-spec.md`: policy schema and evaluation semantics
- `docs/demo-flow.md`: end-to-end execution walkthrough
- `docs/execution-matrix.md`: execution matrix and failure drills
- `examples/*.json`: canonical API payloads and replay records
- `policies/*.yaml`: policy profiles with different strictness
- `configs/runtime.example.yaml`: runtime knobs for limits/timeouts
- `assets/README.md`: expected screenshots and terminal captures

## Core contracts

The reference API surface is intentionally small:

- `POST /api/tasks`
- `POST /api/tasks/{id}/approve`
- `GET /api/tasks/{id}`
- `GET /api/tasks/{id}/replay`
- `POST /api/policies/evaluate`

Canonical request and event examples:

- task creation: `examples/task-create.json`
- approval response: `examples/approval-event.json`
- terminal task result: `examples/task-result.json`
- replay metadata: `examples/replay-record.json`

## Safety model

Execution is constrained by policy, not prompts.

- Policy engine evaluates each proposed action before side effects.
- Sensitive operations require human approval with TTL.
- Denials and overrides are appended to immutable audit records.
- Session replay links each DOM action to policy and approval context.

See `docs/policy-spec.md` and `policies/default-policy.yaml`.

## Quick walkthrough

1. Submit a task payload from `examples/task-create.json`.
2. Runner emits proposed actions and requests approval if required.
3. Reviewer submits an approval payload from `examples/approval-event.json`.
4. Runtime executes allowed steps and emits `examples/task-result.json`.
5. Replay endpoint exposes action timeline and screenshots metadata.

`docs/demo-flow.md` contains a full happy-path plus failure injection.

## Failure handling

The reference model handles:

- selector drift (`ElementNotFound`)
- navigation timeout (`NavigationTimeout`)
- policy denial (`PolicyDenied`)
- approval timeout (`ApprovalExpired`)
- side-effect conflict (`IdempotencyConflict`)

Recovery procedures and retry envelopes are listed in `docs/execution-matrix.md`.

## Non-goals

- generic chat interface design
- prompt cataloging
- vendor-specific orchestration lock-in

## Screenshots and artifacts

Store media in `assets/` using the conventions in `assets/README.md`.
