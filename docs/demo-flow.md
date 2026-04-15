# Demo Flow

The demo set in `demo/` was generated from the live Azure planner path and then evaluated by the local policy engine.

## Read-only inspection

- Input: `demo/input/task-readonly.json`
- Task result: `demo/output/task-readonly-create.json`
- Replay: `demo/output/replay-readonly-initial.json`

Observed behavior:

- planner emitted a six-step navigation and inspection plan
- every action matched an allow rule
- task completed without approval

## Approval-gated mutation

- Input: `demo/input/task-approval.json`
- Initial task: `demo/output/task-approval-create.json`
- Approval event: `demo/output/approve-approval-01.json`
- Final task: `demo/output/task-approval-final.json`
- Final replay: `demo/output/replay-approval-final.json`

Observed behavior:

- planner emitted a five-step mutation plan
- navigation and discovery steps were allowed
- the final `submit_form` action matched `gate-writes`
- approval resumed execution and the task reached `succeeded`

## Policy denial

- Input: `demo/input/task-denied.json`
- Task result: `demo/output/task-denied-create.json`
- Replay: `demo/output/replay-denied-initial.json`

Observed behavior:

- planner emitted an external-portal export plan
- first `navigate` action failed policy because no allow rule matched the external base URL
- task terminated with `PolicyDenied`
