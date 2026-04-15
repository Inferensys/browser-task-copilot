from __future__ import annotations

import json
import re
from typing import Any, Dict, List
from urllib.parse import urljoin

from openai import AzureOpenAI

from .config import Settings
from .models import ActionType, PlannerMode, PlannerTrace, ProposedAction, TaskCreateRequest
from .planner import PlanningError, PlanningResult


class AzureActionPlanner:
    def __init__(self, settings: Settings) -> None:
        settings.validate_for_live_mode()
        self._settings = settings
        self._client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
            max_retries=2,
            timeout=90.0,
        )

    def plan(self, task_id: str, req: TaskCreateRequest) -> PlanningResult:
        allowed_action_types = ["navigate", "read_dom", "click", "type", "submit_form"]
        if req.constraints.allow_file_downloads:
            allowed_action_types.append("download")
        if "upload" in req.intent.lower():
            allowed_action_types.append("upload")

        try:
            response = self._client.chat.completions.create(
                model=self._settings.azure_openai_planner_deployment,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a browser task planner for a guarded control plane. "
                            "Return a minimal action plan that another service will review against policy. "
                            "Do not explain outside the tool call. "
                            "Use only the provided base_url as the navigation root. "
                            "Prefer read_dom for inspection work, and prefer a single submit_form over many type "
                            "actions when the write can be represented as structured form submission. "
                            "Do not invent credentials, authentication steps, or hidden application routes. "
                            "Keep selectors stable and terse when you need them. "
                            "If the request is underspecified, return an empty action list with a rationale."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "intent": req.intent,
                                "target": {
                                    "base_url": req.target.base_url,
                                    "workspace": req.target.workspace,
                                },
                                "context": req.context.model_dump(mode="json"),
                                "constraints": req.constraints.model_dump(mode="json"),
                                "allowed_action_types": allowed_action_types,
                            },
                            ensure_ascii=True,
                        ),
                    },
                ],
                tools=[_browser_plan_schema(allowed_action_types)],
                tool_choice={"type": "function", "function": {"name": "propose_browser_plan"}},
            )
        except Exception as exc:  # pragma: no cover - exercised in live demo only
            raise PlanningError(f"Azure planner request failed: {exc}") from exc

        tool_calls = response.choices[0].message.tool_calls or []
        if not tool_calls:
            raise PlanningError("Azure planner returned no tool call.")

        arguments = json.loads(tool_calls[0].function.arguments)
        raw_actions = arguments.get("actions", [])
        warnings: List[str] = []
        actions = self._normalize_actions(task_id, req, raw_actions, warnings)
        max_actions = req.constraints.max_actions
        if max_actions and len(actions) > max_actions:
            actions = actions[:max_actions]
            warnings.append(f"Truncated model output to request max_actions={max_actions}.")

        return PlanningResult(
            actions=actions,
            trace=PlannerTrace(
                mode=PlannerMode.AZURE,
                provider="azure-openai",
                model=self._settings.azure_openai_planner_deployment,
                confidence=_coerce_confidence(arguments.get("confidence")),
                rationale=arguments.get("rationale"),
                warnings=warnings,
            ),
        )

    def _normalize_actions(
        self,
        task_id: str,
        req: TaskCreateRequest,
        raw_actions: List[Dict[str, Any]],
        warnings: List[str],
    ) -> List[ProposedAction]:
        base_url = req.target.base_url.rstrip("/") + "/"
        actions: List[ProposedAction] = []
        used_action_ids: set[str] = set()

        for index, raw_action in enumerate(raw_actions, start=1):
            raw_type = raw_action.get("type")
            try:
                action_type = ActionType(raw_type)
            except ValueError as exc:
                raise PlanningError(f"Azure planner returned unsupported action type: {raw_type}") from exc

            target = dict(raw_action.get("target") or {})
            if action_type in {ActionType.NAVIGATE, ActionType.SUBMIT_FORM, ActionType.DOWNLOAD}:
                url = target.get("url")
                if isinstance(url, str) and url:
                    target["url"] = url if "://" in url else urljoin(base_url, url.lstrip("/"))
                elif action_type == ActionType.NAVIGATE:
                    target["url"] = base_url

            metadata = dict(raw_action.get("metadata") or {})
            description = raw_action.get("description")
            if isinstance(description, str) and description:
                metadata.setdefault("description", description)

            slug = _sanitize_slug(raw_action.get("slug") or f"{index:02d}_{action_type.value}")
            action_id = f"{task_id}_{slug}"
            if action_id in used_action_ids:
                action_id = f"{task_id}_{index:02d}_{slug}"
            used_action_ids.add(action_id)

            actions.append(
                ProposedAction(
                    action_id=action_id,
                    type=action_type,
                    target=target,
                    metadata=metadata,
                )
            )

        if not actions:
            warnings.append("Planner returned an empty action plan.")
        return actions


def _browser_plan_schema(allowed_action_types: List[str]) -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "propose_browser_plan",
            "description": "Propose a typed browser action plan for a guarded executor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "confidence": {
                        "type": "number",
                        "description": "Planner confidence between 0 and 1.",
                    },
                    "rationale": {
                        "type": "string",
                        "description": "Short explanation for the chosen plan shape.",
                    },
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "slug": {
                                    "type": "string",
                                    "description": "Short stable identifier used in the action_id suffix.",
                                },
                                "type": {
                                    "type": "string",
                                    "enum": allowed_action_types,
                                },
                                "description": {
                                    "type": "string",
                                    "description": "Human-readable step intent.",
                                },
                                "target": {
                                    "type": "object",
                                    "description": "Action target payload such as url, selector, or form fields.",
                                },
                                "metadata": {
                                    "type": "object",
                                    "description": "Optional structured annotations carried through replay and audit.",
                                },
                            },
                            "required": ["slug", "type", "description", "target", "metadata"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["confidence", "rationale", "actions"],
                "additionalProperties": False,
            },
        },
    }


def _sanitize_slug(raw_value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "_", raw_value.lower()).strip("_")
    return cleaned or "step"


def _coerce_confidence(value: Any) -> float | None:
    if value is None:
        return None
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, confidence))
