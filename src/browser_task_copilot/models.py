from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    NAVIGATE = "navigate"
    READ_DOM = "read_dom"
    CLICK = "click"
    TYPE = "type"
    SUBMIT_FORM = "submit_form"
    DOWNLOAD = "download"
    UPLOAD = "upload"


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TaskTarget(BaseModel):
    base_url: str
    workspace: Optional[str] = None


class TaskContext(BaseModel):
    tenant: Optional[str] = None
    requester: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class TaskConstraints(BaseModel):
    max_actions: Optional[int] = None
    task_timeout_seconds: Optional[int] = None
    allow_file_downloads: bool = False


class TaskCreateRequest(BaseModel):
    task_id: Optional[str] = None
    intent: str
    target: TaskTarget
    context: TaskContext = Field(default_factory=TaskContext)
    constraints: TaskConstraints = Field(default_factory=TaskConstraints)
    policy_profile: str = Field(default="default")


class ProposedAction(BaseModel):
    action_id: str
    type: ActionType
    target: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PolicyDefaults(BaseModel):
    decision: PolicyDecision
    task_timeout_seconds: int = 300
    approval_ttl_seconds: int = 300
    max_actions: int = 40


class ApprovalSettings(BaseModel):
    roles_allowed: List[str] = Field(default_factory=list)
    scope: str = "action"
    require_reason: bool = False


class PolicyRule(BaseModel):
    name: str
    when: Dict[str, Any] = Field(default_factory=dict)
    then: Dict[str, Any] = Field(default_factory=dict)


class PolicyDocument(BaseModel):
    version: str
    defaults: PolicyDefaults
    approvals: ApprovalSettings = Field(default_factory=ApprovalSettings)
    rules: List[PolicyRule] = Field(default_factory=list)


class PolicyEvaluationRequest(BaseModel):
    policy_profile: str = "default"
    action: ProposedAction
    context: TaskContext = Field(default_factory=TaskContext)


class PolicyEvaluationResponse(BaseModel):
    policy_profile: str
    action_id: str
    decision: PolicyDecision
    matched_rule: Optional[str] = None
    reason: str


class ApproverIdentity(BaseModel):
    user_id: Optional[str] = None
    email: str
    role: str


class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    DENIED = "denied"


class ApprovalRequest(BaseModel):
    action_id: str
    decision: ApprovalDecision
    approved_by: ApproverIdentity
    reason: Optional[str] = None
    signature: Optional[str] = None


class PendingApproval(BaseModel):
    action_id: str
    expires_at: datetime
    roles_allowed: List[str] = Field(default_factory=list)
    requested_at: datetime


class ReplayEvent(BaseModel):
    t: datetime
    action_id: str
    decision: str
    screenshot: Optional[str] = None
    approval_id: Optional[str] = None
    approved_by: Optional[str] = None
    detail: Optional[str] = None


class ReplayRecord(BaseModel):
    replay_id: str
    task_id: str
    timeline: List[ReplayEvent] = Field(default_factory=list)


class TaskSummary(BaseModel):
    actions_total: int = 0
    actions_executed: int = 0
    actions_skipped: int = 0
    policy_denials: int = 0
    approvals_used: int = 0


class TaskArtifacts(BaseModel):
    replay_id: str
    trace_uri: str
    screenshots_prefix: str


class TaskRecord(BaseModel):
    task_id: str
    intent: str
    policy_profile: str
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    context: TaskContext = Field(default_factory=TaskContext)
    actions: List[ProposedAction] = Field(default_factory=list)
    next_action_index: int = 0
    pending_approval: Optional[PendingApproval] = None
    summary: TaskSummary = Field(default_factory=TaskSummary)
    artifacts: Optional[TaskArtifacts] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    pending_approval: Optional[PendingApproval] = None
    summary: TaskSummary
    artifacts: Optional[TaskArtifacts] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
