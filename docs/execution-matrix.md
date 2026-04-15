# Execution Matrix

This document defines reproducible task scenarios used to validate runtime behavior, policy controls, and replay quality.

## Scenario A: Low-risk read path

- Goal: collect invoice status from admin dashboard
- Expected approvals: none
- Policy profile: `policies/default-policy.yaml`
- Success condition:
  - all actions marked `allow`
  - no mutation events in replay
  - completion under `task_timeout_seconds`

## Scenario B: Guarded write path

- Goal: update account credit limit
- Expected approvals: one high-risk approval before submit
- Policy profile: `policies/high-risk-policy.yaml`
- Success condition:
  - write actions blocked until approval
  - approval linked to specific `action_id`
  - audit trail stores approver and expiry

## Scenario C: Selector drift recovery

- Fault injection: replace primary selector during run
- Runtime expectation:
  - mark step as `retryable`
  - attempt alternate selectors by priority
  - fail with `ElementNotFound` if alternates exhausted

## Scenario D: Approval timeout

- Fault injection: do not submit approval before TTL
- Runtime expectation:
  - transition task state to `blocked_expired`
  - emit event `approval.expired`
  - prevent replay from showing any blocked side effect

## Scenario E: Partial completion with idempotent resume

- Fault injection: network reset after side effect
- Runtime expectation:
  - emit checkpoint with `idempotency_key`
  - resume from last committed checkpoint
  - never duplicate form submission

## Artifact checklist

For each scenario, capture:

- `task request` payload
- `policy decision` log
- `approval event` payload (if applicable)
- `terminal task result` payload
- `replay metadata` JSON
- one screenshot per state transition
