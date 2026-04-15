from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException

from .models import (
    ApprovalRequest,
    PolicyEvaluationRequest,
    PolicyEvaluationResponse,
    TaskCreateRequest,
    TaskResponse,
)
from .policy import PolicyEngine, PolicyLoader, PolicyNotFoundError
from .service import (
    ApprovalExpiredError,
    InvalidStateError,
    PermissionDeniedError,
    TaskNotFoundError,
    TaskService,
)
from .store import InMemoryTaskStore


def create_app() -> FastAPI:
    app = FastAPI(title="browser-task-copilot", version="0.1.0")
    repo_root = Path(__file__).resolve().parents[2]
    policy_loader = PolicyLoader(repo_root / "policies")
    service = TaskService(
        store=InMemoryTaskStore(),
        policy_loader=policy_loader,
        policy_engine=PolicyEngine(),
    )
    app.state.task_service = service

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.post("/api/tasks", response_model=TaskResponse)
    def create_task(payload: TaskCreateRequest):
        try:
            return service.create_task(payload)
        except PolicyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/tasks/{task_id}", response_model=TaskResponse)
    def get_task(task_id: str):
        try:
            return service.get_task(task_id)
        except TaskNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"task '{task_id}' not found") from exc

    @app.post("/api/tasks/{task_id}/approve", response_model=TaskResponse)
    def approve_task(task_id: str, payload: ApprovalRequest):
        try:
            return service.approve_task(task_id, payload)
        except TaskNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"task '{task_id}' not found") from exc
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ApprovalExpiredError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except InvalidStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except PolicyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/tasks/{task_id}/replay")
    def get_task_replay(task_id: str):
        try:
            return service.get_replay(task_id)
        except TaskNotFoundError as exc:
            raise HTTPException(status_code=404, detail=f"task '{task_id}' not found") from exc

    @app.post("/api/policies/evaluate", response_model=PolicyEvaluationResponse)
    def evaluate_policy(payload: PolicyEvaluationRequest):
        try:
            decision, matched_rule, reason = service.evaluate_policy(
                payload.policy_profile, payload.action, payload.context
            )
        except PolicyNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return PolicyEvaluationResponse(
            policy_profile=payload.policy_profile,
            action_id=payload.action.action_id,
            decision=decision,
            matched_rule=matched_rule,
            reason=reason,
        )

    return app


app = create_app()
