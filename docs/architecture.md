# Architecture Notes

## Implemented boundary

This repository currently implements a control plane, not a full browser worker.

- Intent expansion can be deterministic or Azure-backed.
- Policy evaluation is always local and deterministic.
- Approval issuance and validation are always local and deterministic.
- Execution is simulated by advancing a replay timeline rather than driving a browser session.

## Request flow

1. `POST /api/tasks` receives intent, target, context, constraints, and policy profile.
2. The planner expands intent into a typed action list.
3. Each action is evaluated against the selected YAML policy.
4. `allow` advances the replay timeline.
5. `require_approval` pauses the task and creates a `PendingApproval`.
6. `deny` fails the task immediately and records the denial in replay.

## Domain objects

- `TaskCreateRequest`: external API request for a new browser task.
- `ProposedAction`: normalized planner output consumed by the policy engine.
- `PlannerTrace`: provider, model, confidence, and rationale attached to the task record.
- `ReplayRecord`: ordered list of policy and approval decisions for the task.

## Task states

- `pending`
- `running`
- `waiting_approval`
- `succeeded`
- `failed`

The service does not expose intermediate planning-only states; planning happens inline during task creation.

## Why the planner is isolated

`service.py` owns lifecycle and policy mechanics. Planner implementations only return `PlanningResult`:

- `DeterministicActionPlanner` keeps tests stable and makes offline runs predictable.
- `AzureActionPlanner` handles provider-specific prompting, tool calling, and normalization.

This keeps provider logic out of the state machine and makes it straightforward to add another backend without rewriting approval or replay handling.

## Replay model

Replay entries capture:

- action id
- policy decision
- approval id when relevant
- approver identity when relevant
- simulated screenshot URI
- rule-match detail

The URIs are placeholders for a future executor-backed artifact store.
