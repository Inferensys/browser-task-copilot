# Azure Foundry Notes

## Required environment

```bash
export BROWSER_TASK_COPILOT_PROVIDER=azure
export AZURE_OPENAI_ENDPOINT="https://<resource>.openai.azure.com/"
export AZURE_OPENAI_API_KEY="<key>"
export AZURE_OPENAI_API_VERSION="2025-04-01-preview"
export AZURE_OPENAI_PLANNER_DEPLOYMENT="gpt-5-mini"
```

The live planner is isolated to `src/browser_task_copilot/azure_planner.py`. Everything after normalization stays provider-agnostic.

## Deployment shape used here

- Planner tier: `gpt-5-mini`
- Heavier adjudication tier if you extend the service: `gpt-5.4`

This repository only calls the planner tier today. The heavier tier is noted because it is a natural place to add secondary review or tool-result adjudication without changing the policy boundary.

## Validation

Run the live demo generator:

```bash
uv run python scripts/run_live_demo.py
```

The script writes:

- request payloads into `demo/input/`
- live task results into `demo/output/`
- a scenario index into `demo/output/demo-summary.json`

## Provider portability

The portability surface is the `ActionPlanner` interface:

- provider implementation accepts `TaskCreateRequest`
- provider returns `PlanningResult`
- returned actions are normalized into `ProposedAction`
- policy engine and approval flow remain unchanged

Equivalent integrations:

- Vertex AI: implement a planner client that uses a tool-calling Gemini model and map its structured arguments into `PlanningResult`
- Anthropic or Bedrock: use tool use or JSON-schema output and map the provider response into the same action contract
- OpenAI API: swap `AzureOpenAI` for the standard client while keeping the tool schema and normalization logic

If you add another provider, keep the provider-specific prompt and client setup in a separate module and do not let policy decisions depend on provider output metadata.
