from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Protocol
from urllib.parse import urljoin

from .config import Settings
from .models import PlannerMode, PlannerTrace, ProposedAction, TaskCreateRequest


class PlanningError(RuntimeError):
    pass


@dataclass(frozen=True)
class PlanningResult:
    actions: List[ProposedAction]
    trace: PlannerTrace


class ActionPlanner(Protocol):
    def plan(self, task_id: str, req: TaskCreateRequest) -> PlanningResult:
        ...


class DeterministicActionPlanner:
    def plan(self, task_id: str, req: TaskCreateRequest) -> PlanningResult:
        intent_lower = req.intent.lower()
        base_url = _normalize_base_url(req.target.base_url)
        workspace = req.target.workspace
        account_ref = _extract_account_ref(req.intent)

        actions: List[ProposedAction] = [
            ProposedAction(
                action_id=f"{task_id}_open_workspace",
                type="navigate",
                target={"url": base_url, "workspace": workspace},
                metadata={
                    "description": "Open the operator workspace root.",
                    "account_ref": account_ref,
                },
            )
        ]

        warnings: List[str] = []
        if _looks_read_only_intent(intent_lower):
            actions.append(
                ProposedAction(
                    action_id=f"{task_id}_inspect_account_snapshot",
                    type="read_dom",
                    target={"url": urljoin(base_url, "accounts"), "account_ref": account_ref},
                    metadata={
                        "description": "Inspect the account page and extract the current state.",
                        "intent": req.intent,
                    },
                )
            )
        elif _looks_mutating_intent(intent_lower):
            actions.extend(
                [
                    ProposedAction(
                        action_id=f"{task_id}_open_account_search",
                        type="click",
                        target={"selector": "#account-search"},
                        metadata={
                            "description": "Focus the account search control.",
                            "account_ref": account_ref,
                        },
                    ),
                    ProposedAction(
                        action_id=f"{task_id}_submit_change",
                        type="submit_form",
                        target={
                            "url": urljoin(base_url, "accounts/update-credit-limit"),
                            "account_ref": account_ref,
                        },
                        metadata={
                            "description": "Submit the account update request.",
                            "intent": req.intent,
                        },
                    ),
                ]
            )
        elif _looks_download_intent(intent_lower) and req.constraints.allow_file_downloads:
            actions.extend(
                [
                    ProposedAction(
                        action_id=f"{task_id}_inspect_export_view",
                        type="read_dom",
                        target={"url": urljoin(base_url, "exports"), "account_ref": account_ref},
                        metadata={"description": "Inspect the export view before generating a file."},
                    ),
                    ProposedAction(
                        action_id=f"{task_id}_download_export",
                        type="download",
                        target={"url": urljoin(base_url, "exports/current.csv")},
                        metadata={"description": "Download the requested export artifact."},
                    ),
                ]
            )
        else:
            actions.append(
                ProposedAction(
                    action_id=f"{task_id}_inspect_account_snapshot",
                    type="read_dom",
                    target={"url": urljoin(base_url, "accounts"), "account_ref": account_ref},
                    metadata={
                        "description": "Inspect the account page and extract the current state.",
                        "intent": req.intent,
                    },
                )
            )

        if "upload" in intent_lower:
            actions.append(
                ProposedAction(
                    action_id=f"{task_id}_upload_attachment",
                    type="upload",
                    target={"selector": "input[type=file]"},
                    metadata={"description": "Upload an operator-supplied attachment."},
                )
            )

        max_actions = req.constraints.max_actions
        if max_actions and len(actions) > max_actions:
            actions = actions[:max_actions]
            warnings.append(f"Truncated action plan to request max_actions={max_actions}.")

        return PlanningResult(
            actions=actions,
            trace=PlannerTrace(
                mode=PlannerMode.DETERMINISTIC,
                provider="builtin",
                rationale=(
                    "Rule-based planner expanded the request using lexical intent hints and "
                    "the provided target context."
                ),
                warnings=warnings,
            ),
        )


def build_action_planner(settings: Settings) -> ActionPlanner:
    if settings.live_provider_enabled:
        from .azure_planner import AzureActionPlanner

        return AzureActionPlanner(settings)
    return DeterministicActionPlanner()


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/"


def _extract_account_ref(text: str) -> str | None:
    match = re.search(r"\b[A-Z]{2,}(?:-[A-Z0-9]+)+\b", text)
    if match:
        return match.group(0)
    fallback = re.search(r"\b(?:account|invoice|order)\s+([A-Z0-9-]{4,})\b", text, flags=re.IGNORECASE)
    if fallback:
        return fallback.group(1)
    return None


def _looks_mutating_intent(intent_lower: str) -> bool:
    keywords = (
        "increase",
        "decrease",
        "update",
        "change",
        "edit",
        "set",
        "submit",
        "create",
        "delete",
        "apply",
        "approve",
    )
    return any(keyword in intent_lower for keyword in keywords)


def _looks_download_intent(intent_lower: str) -> bool:
    keywords = ("download", "export", "csv", "spreadsheet", "report")
    return any(keyword in intent_lower for keyword in keywords)


def _looks_read_only_intent(intent_lower: str) -> bool:
    guardrails = (
        "without making changes",
        "without changing",
        "without edits",
        "do not make changes",
        "don't make changes",
        "read only",
        "readonly",
        "summarize",
        "inspect",
    )
    return any(guardrail in intent_lower for guardrail in guardrails)
