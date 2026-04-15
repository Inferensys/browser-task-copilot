# Demo Flow

This flow uses contract artifacts in `examples/` and policies in `policies/`.

## Happy path: guarded account update

1. Create task
   - request body: `examples/task-create.json`
   - expected state: `planning`
2. Policy evaluation
   - read actions: `allow`
   - write action (`submit_form`): `require_approval`
   - expected state: `awaiting_approval`
3. Submit approval
   - request body: `examples/approval-event.json`
   - expected state: `running`
4. Runner completion
   - terminal payload: `examples/task-result.json`
   - expected state: `succeeded`
5. Replay retrieval
   - metadata file: `examples/replay-record.json`
   - verify every side effect has policy and approval linkage

## Failure path: approval timeout

1. Create task as above.
2. Do not submit approval before `approval_ttl_seconds`.
3. Runtime transitions to `blocked_expired`.
4. Verify no write action executed.

## Failure path: selector drift

1. Inject DOM change for primary selector.
2. Runner attempts fallback selector set.
3. If fallback set exhausted, terminal error should be `ElementNotFound`.
4. Replay includes attempt order and selector snapshot hashes.
