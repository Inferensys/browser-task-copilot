# Policy Spec

Policies are evaluated per action proposal before runner execution.

## Schema

Top-level keys:

- `version`: policy schema version
- `defaults`: default behavior and runtime limits
- `rules`: ordered match/action clauses
- `approvals`: approval requirements by risk class

## Action classification

Supported action categories:

- `navigate`
- `read_dom`
- `click`
- `type`
- `submit_form`
- `download`
- `upload`

Supported risk levels:

- `low`
- `medium`
- `high`
- `critical`

## Decision outcomes

- `allow`: action executes immediately
- `deny`: action is rejected and logged
- `require_approval`: action blocks pending approval

## Matching semantics

Rule order is first-match-wins. Matchable fields:

- `action.type`
- `target.url`
- `target.selector`
- `context.tenant`
- `context.tags`

## Approval semantics

Approvals are scoped to a single action unless `scope: task` is set.

Required fields:

- `task_id`
- `action_id`
- `approved_by`
- `expires_at`
- `reason`

Runtime must reject approval payloads where:

- `expires_at` is in the past
- approver role does not satisfy policy
- referenced action hash does not match original proposal
