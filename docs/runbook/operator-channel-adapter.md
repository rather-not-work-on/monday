# Operator Channel Adapter Runbook

## Goal
Run the monday operator-channel delivery baseline deterministically and confirm that Slack-facing payloads remain thin wrappers over the messaging adapter contract.

## Contract Inputs
- runbook contract: `config/operator-channel-adapter-runbook-contract.json`
- CLI entrypoint: `scripts/send_operator_message.py`
- payload boundary: `packages/contract-bindings/src/operator_channels.ts`
- adapter baseline: `packages/messaging-adapter/src/operator_channel_adapter.ts`

## Command (Dry Run)
```bash
RUN_ID="operator-channel-$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="/tmp/monday-operator-channel-$RUN_ID"
mkdir -p "$OUT_DIR"

cat >"$OUT_DIR/operator-message.json" <<'JSON'
{
  "messageClass": "status_update",
  "deliveryMode": "dry-run",
  "goalKey": "uap-goal-driven-autonomy-wave1",
  "body": "operator update",
  "runId": "run-123",
  "target": {
    "channelKind": "slack_skill_cli",
    "deliveryTarget": "slack://monday/thread-1",
    "threadRef": "thread-1"
  }
}
JSON

python3 scripts/send_operator_message.py \
  --payload-file "$OUT_DIR/operator-message.json" \
  --output "$OUT_DIR/operator-message-report.json"
```

## Command (Apply Gate)
`apply` mode is expected to stay blocked until a reviewed Slack transport is wired behind the CLI/MCP boundary.

```bash
python3 scripts/send_operator_message.py \
  --payload-file "$OUT_DIR/operator-message.json" \
  --mode apply \
  --output "$OUT_DIR/operator-message-apply-report.json"
```

Expected gate signal:
- command exits non-zero
- `operator-message-apply-report.json` has `verdict=fail`
- `deliveryVerdict=blocked`
- `errors` contains `operator_transport_not_configured`

## Skill Boundary
- monday skills should call `scripts/send_operator_message.py` directly or invoke an MCP wrapper that forwards the same payload shape
- `slack_skill_cli` and `slack_skill_mcp` are the only supported channel kinds at this baseline
- payload semantics and idempotency stay in `packages/messaging-adapter`, not in the skill prompt
- transport-specific Slack API behavior lands in a follow-up adapter card, not in the runbook or CLI contract

## Generated Artifacts
- `$OUT_DIR/operator-message.json`
- `$OUT_DIR/operator-message-report.json`
- `$OUT_DIR/operator-message-apply-report.json`

## Healthy Signals
- dry-run report has `verdict=pass`
- dry-run report has `deliveryVerdict=dry_run`
- `channelKind=slack_skill_cli` or `channelKind=slack_skill_mcp`
- apply gate fails closed with `operator_transport_not_configured`

## Rollback Trigger
Trigger rollback if one of:
1. dry-run report is not `verdict=pass`
2. operator payload stops requiring `goalKey` or `body`
3. apply gate returns success without a reviewed transport implementation

Immediate action:
- stop operator message rollout
- preserve `$OUT_DIR` evidence
- open a follow-up issue with `operator_channel_adapter_contract_regression`
