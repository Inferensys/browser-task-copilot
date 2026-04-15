# Architecture Notes

## Design goals

- Keep control-plane contracts stable across execution backends.
- Isolate browser side effects behind explicit policy + approval checks.
- Produce replay and audit artifacts sufficient for post-incident analysis.

## Logical components

1. Task API
   - accepts task intent, constraints, and context handles
   - creates task state machine instance
2. Planner
   - expands intent into candidate browser actions
   - attaches confidence and risk labels per action
3. Policy engine
   - evaluates each candidate action against YAML policy
   - returns `allow`, `deny`, or `require_approval`
4. Approval service
   - issues short-lived approval requests for gated actions
   - validates approver identity and expiry
5. Runner
   - executes allowed actions against browser session
   - reports checkpoints and captures replay artifacts
6. Artifact store
   - stores screenshots, action timeline, and policy decisions
7. Audit writer
   - appends immutable event log for all state transitions

## Task state machine

- `queued`
- `planning`
- `awaiting_approval`
- `running`
- `blocked_expired`
- `succeeded`
- `failed`

Transitions are event-driven and monotonic.

## Data contracts

- Task request schema: `examples/task-create.json`
- Approval schema: `examples/approval-event.json`
- Task terminal schema: `examples/task-result.json`
- Replay schema: `examples/replay-record.json`

## Security boundaries

- Browser sessions run in isolated worker scope.
- Secrets are referenced by handle, never embedded in prompts.
- Policy decisions are detached from model output and must pass explicit checks.
- Approval tokens are one-time use and bound to `task_id + action_id`.
