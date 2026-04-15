from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml

from .models import PolicyDecision, PolicyDocument, ProposedAction, TaskContext


class PolicyNotFoundError(Exception):
    pass


class PolicyLoader:
    def __init__(self, policy_dir: Path) -> None:
        self._policy_dir = policy_dir
        self._cache: Dict[str, PolicyDocument] = {}

    def get(self, profile: str) -> PolicyDocument:
        if profile in self._cache:
            return self._cache[profile]

        path = self._policy_dir / f"{profile}-policy.yaml"
        if not path.exists():
            raise PolicyNotFoundError(f"policy profile '{profile}' not found")

        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        policy = PolicyDocument.model_validate(data)
        self._cache[profile] = policy
        return policy


class PolicyEngine:
    def evaluate(
        self, policy: PolicyDocument, action: ProposedAction, context: TaskContext
    ) -> Tuple[PolicyDecision, Optional[str], str]:
        for rule in policy.rules:
            if self._matches(rule.when, action, context):
                decision_raw = rule.then.get("decision", policy.defaults.decision.value)
                decision = PolicyDecision(decision_raw)
                return decision, rule.name, f"matched rule '{rule.name}'"

        return (
            policy.defaults.decision,
            None,
            "no rule matched; using policy defaults",
        )

    def _matches(
        self, when: Dict[str, Any], action: ProposedAction, context: TaskContext
    ) -> bool:
        for key, expected in when.items():
            if key == "action.type":
                if action.type.value != expected:
                    return False
                continue
            if key == "action.type_in":
                values = set(expected or [])
                if action.type.value not in values:
                    return False
                continue
            if key == "target.url_prefix":
                url = str(action.target.get("url", ""))
                if not url.startswith(str(expected)):
                    return False
                continue
            if key == "target.url":
                url = str(action.target.get("url", ""))
                if url != str(expected):
                    return False
                continue
            if key == "target.selector":
                selector = str(action.target.get("selector", ""))
                if selector != str(expected):
                    return False
                continue
            if key == "context.tenant":
                if (context.tenant or "") != str(expected):
                    return False
                continue
            if key == "context.tags":
                expected_tags = set(expected or [])
                actual_tags = set(context.tags or [])
                if not expected_tags.issubset(actual_tags):
                    return False
                continue
            return False

        return True
