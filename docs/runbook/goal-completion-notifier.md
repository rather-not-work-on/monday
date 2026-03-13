# Goal Completion Notifier Runbook

## Goal
Run the monday-owned goal completion notification baseline deterministically and confirm that the payload contract remains stable before a real email transport is wired.

## Contract Inputs
- runbook contract: `config/goal-completion-notifier-runbook-contract.json`
- CLI entrypoint: `scripts/send_goal_completion_notification.py`
- payload boundary: `packages/contract-bindings/src/operator_channels.ts`
- notifier baseline: `packages/messaging-adapter/src/goal_completion_notifier.ts`

## Command (Dry Run)
```bash
RUN_ID="goal-completion-$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="/tmp/monday-goal-completion-$RUN_ID"
mkdir -p "$OUT_DIR"

cat >"$OUT_DIR/goal-completion.json" <<'JSON'
{
  "messageClass": "goal_completed",
  "deliveryMode": "dry-run",
  "goalKey": "uap-goal-driven-autonomy-wave1",
  "body": "goal completed",
  "achievedAtUtc": "2026-03-13T00:00:00Z",
  "target": {
    "channelKind": "email_cli",
    "deliveryTarget": "mailto:operator@example.com"
  }
}
JSON

python3 scripts/send_goal_completion_notification.py \
  --payload-file "$OUT_DIR/goal-completion.json" \
  --output "$OUT_DIR/goal-completion-notification-report.json"
```

## Command (Apply Gate)
`apply` mode is expected to stay blocked until a real email transport adapter is wired.

```bash
python3 scripts/send_goal_completion_notification.py \
  --payload-file "$OUT_DIR/goal-completion.json" \
  --mode apply \
  --output "$OUT_DIR/goal-completion-notification-apply-report.json"
```

Expected gate signal:
- command exits non-zero
- `goal-completion-notification-apply-report.json` has `verdict=fail`
- `deliveryVerdict=blocked`
- `errors` contains `goal_completion_transport_not_configured`

## Generated Artifacts
- `$OUT_DIR/goal-completion.json`
- `$OUT_DIR/goal-completion-notification-report.json`
- `$OUT_DIR/goal-completion-notification-apply-report.json`

## Healthy Signals
- dry-run report has `verdict=pass`
- dry-run report has `deliveryVerdict=dry_run`
- `messageClass=goal_completed`
- `channelKind=email_cli` or `channelKind=email_mcp`
- apply gate fails closed with `goal_completion_transport_not_configured`

## Rollback Trigger
Trigger rollback if one of:
1. dry-run report is not `verdict=pass`
2. goal completion payload stops requiring `achievedAtUtc`
3. apply gate returns success without a reviewed transport implementation

Immediate action:
- stop notification rollout
- preserve `$OUT_DIR` evidence
- open a follow-up issue with `goal_completion_notification_contract_regression`
