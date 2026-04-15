from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable, Optional
from uuid import uuid4

from .models import (
    ApprovalDecision,
    ApprovalRequest,
    PendingApproval,
    PolicyDecision,
    ProposedAction,
    ReplayEvent,
    ReplayRecord,
    TaskArtifacts,
    TaskContext,
    TaskCreateRequest,
    TaskRecord,
    TaskResponse,
    TaskStatus,
    TaskSummary,
)
from .planner import ActionPlanner
from .policy import PolicyEngine, PolicyLoader, PolicyNotFoundError
from .store import InMemoryTaskStore


class TaskNotFoundError(Exception):
    pass


class InvalidStateError(Exception):
    pass


class ApprovalExpiredError(Exception):
    pass


class PermissionDeniedError(Exception):
    pass


class TaskService:
    def __init__(
        self,
        store: InMemoryTaskStore,
        policy_loader: PolicyLoader,
        policy_engine: PolicyEngine,
        planner: ActionPlanner,
        now_provider: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._store = store
        self._policy_loader = policy_loader
        self._policy_engine = policy_engine
        self._planner = planner
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def create_task(self, req: TaskCreateRequest) -> TaskResponse:
        task_id = req.task_id or f"task_{uuid4().hex[:16]}"
        now = self._now_provider()
        plan = self._planner.plan(task_id, req)
        replay_id = f"replay_{uuid4().hex[:8]}"
        task = TaskRecord(
            task_id=task_id,
            intent=req.intent,
            policy_profile=req.policy_profile,
            status=TaskStatus.PENDING,
            created_at=now,
            context=req.context,
            actions=plan.actions,
            planner=plan.trace,
            summary=TaskSummary(actions_total=len(plan.actions)),
            artifacts=TaskArtifacts(
                replay_id=replay_id,
                trace_uri=f"memory://{replay_id}/trace.json",
                screenshots_prefix=f"memory://{replay_id}/screenshots/",
            ),
        )
        replay = ReplayRecord(replay_id=replay_id, task_id=task_id, timeline=[])
        self._store.save_task(task)
        self._store.save_replay(replay)
        self._run_until_blocked(task_id)
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> TaskResponse:
        task = self._load_task(task_id)
        self._expire_pending_if_needed(task)
        self._store.save_task(task)
        return self._to_response(task)

    def get_replay(self, task_id: str) -> ReplayRecord:
        replay = self._store.get_replay(task_id)
        if replay is None:
            raise TaskNotFoundError(task_id)
        return replay

    def approve_task(self, task_id: str, req: ApprovalRequest) -> TaskResponse:
        task = self._load_task(task_id)
        self._expire_pending_if_needed(task)
        if task.status == TaskStatus.FAILED and task.error_code == "ApprovalExpired":
            self._store.save_task(task)
            raise ApprovalExpiredError("approval deadline exceeded")
        if task.status != TaskStatus.WAITING_APPROVAL or task.pending_approval is None:
            raise InvalidStateError("task is not waiting for approval")
        if task.pending_approval.action_id != req.action_id:
            raise InvalidStateError("approval action_id does not match pending action")

        policy = self._policy_loader.get(task.policy_profile)
        role = req.approved_by.role
        if role not in policy.approvals.roles_allowed:
            raise PermissionDeniedError(f"role '{role}' is not allowed to approve")
        if policy.approvals.require_reason and not req.reason:
            raise InvalidStateError("approval reason is required by policy")

        now = self._now_provider()
        if now > task.pending_approval.expires_at:
            self._mark_failed(task, "ApprovalExpired", "approval deadline exceeded")
            self._store.save_task(task)
            raise ApprovalExpiredError("approval deadline exceeded")

        replay = self.get_replay(task_id)
        approval_id = f"apr_{uuid4().hex[:12]}"
        replay.timeline.append(
            ReplayEvent(
                t=now,
                action_id=req.action_id,
                decision=req.decision.value,
                approval_id=approval_id,
                approved_by=req.approved_by.email,
                screenshot=f"memory://{replay.replay_id}/screenshots/{len(replay.timeline)+1:03d}.png",
            )
        )
        self._store.save_replay(replay)

        if req.decision == ApprovalDecision.DENIED:
            self._mark_failed(task, "ApprovalDenied", "approval explicitly denied")
            self._store.save_task(task)
            return self._to_response(task)

        task.summary.approvals_used += 1
        task.pending_approval = None
        task.next_action_index += 1
        task.status = TaskStatus.RUNNING
        self._store.save_task(task)
        self._run_until_blocked(task_id)
        return self.get_task(task_id)

    def evaluate_policy(self, profile: str, action: ProposedAction, context: TaskContext):
        policy = self._policy_loader.get(profile)
        decision, rule_name, reason = self._policy_engine.evaluate(policy, action, context)
        return decision, rule_name, reason

    def _run_until_blocked(self, task_id: str) -> None:
        task = self._load_task(task_id)
        if task.status in (TaskStatus.SUCCEEDED, TaskStatus.FAILED):
            return

        if task.started_at is None:
            task.started_at = self._now_provider()
        task.status = TaskStatus.RUNNING
        policy = self._policy_loader.get(task.policy_profile)
        replay = self.get_replay(task_id)

        while task.next_action_index < len(task.actions):
            action = task.actions[task.next_action_index]
            decision, rule_name, reason = self._policy_engine.evaluate(
                policy, action, task.context
            )
            now = self._now_provider()
            replay.timeline.append(
                ReplayEvent(
                    t=now,
                    action_id=action.action_id,
                    decision=decision.value,
                    detail=reason,
                    screenshot=f"memory://{replay.replay_id}/screenshots/{len(replay.timeline)+1:03d}.png",
                )
            )

            if decision == PolicyDecision.DENY:
                task.summary.policy_denials += 1
                self._mark_failed(
                    task,
                    "PolicyDenied",
                    f"action '{action.action_id}' denied by policy ({rule_name or 'defaults'})",
                )
                self._store.save_replay(replay)
                self._store.save_task(task)
                return

            if decision == PolicyDecision.REQUIRE_APPROVAL:
                task.status = TaskStatus.WAITING_APPROVAL
                task.pending_approval = PendingApproval(
                    action_id=action.action_id,
                    requested_at=now,
                    expires_at=now + timedelta(seconds=policy.defaults.approval_ttl_seconds),
                    roles_allowed=policy.approvals.roles_allowed,
                )
                self._store.save_replay(replay)
                self._store.save_task(task)
                return

            task.summary.actions_executed += 1
            task.next_action_index += 1

        task.status = TaskStatus.SUCCEEDED
        task.completed_at = self._now_provider()
        self._store.save_replay(replay)
        self._store.save_task(task)

    def _mark_failed(self, task: TaskRecord, code: str, message: str) -> None:
        task.status = TaskStatus.FAILED
        task.completed_at = self._now_provider()
        task.error_code = code
        task.error_message = message
        task.pending_approval = None

    def _expire_pending_if_needed(self, task: TaskRecord) -> None:
        if task.pending_approval is None or task.status != TaskStatus.WAITING_APPROVAL:
            return
        now = self._now_provider()
        if now > task.pending_approval.expires_at:
            self._mark_failed(task, "ApprovalExpired", "approval deadline exceeded")

    def _load_task(self, task_id: str) -> TaskRecord:
        task = self._store.get_task(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    def _to_response(self, task: TaskRecord) -> TaskResponse:
        return TaskResponse(
            task_id=task.task_id,
            status=task.status,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            actions=task.actions,
            planner=task.planner,
            pending_approval=task.pending_approval,
            summary=task.summary,
            artifacts=task.artifacts,
            error_code=task.error_code,
            error_message=task.error_message,
        )
