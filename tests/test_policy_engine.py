from pathlib import Path

from browser_task_copilot.models import ProposedAction, TaskContext
from browser_task_copilot.policy import PolicyEngine, PolicyLoader


def test_policy_decisions_default_profile() -> None:
    loader = PolicyLoader(Path(__file__).resolve().parents[1] / "policies")
    engine = PolicyEngine()
    policy = loader.get("default")

    allow_action = ProposedAction(
        action_id="a1",
        type="navigate",
        target={"url": "https://ops.internal.example/accounts"},
    )
    decision, rule, _ = engine.evaluate(policy, allow_action, TaskContext())
    assert decision.value == "allow"
    assert rule == "allow-navigation-internal"

    approval_action = ProposedAction(
        action_id="a2",
        type="submit_form",
        target={"url": "https://ops.internal.example/accounts/update-credit-limit"},
    )
    decision, rule, _ = engine.evaluate(policy, approval_action, TaskContext())
    assert decision.value == "require_approval"
    assert rule == "gate-writes"

    deny_action = ProposedAction(action_id="a3", type="upload", target={"selector": "#file"})
    decision, rule, _ = engine.evaluate(policy, deny_action, TaskContext())
    assert decision.value == "deny"
    assert rule == "deny-uploads"
