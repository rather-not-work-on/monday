# PlanningOps Supervisor Handoff Runbook

## Goal
Run the monday-owned supervisor handoff entrypoints deterministically from planningops artifacts so operator status updates and terminal goal-completion notifications stay outside the control plane.

## Contract Inputs
- runbook contract: `config/planningops-supervisor-handoff-runbook-contract.json`
- handoff contract: `planningops/contracts/supervisor-operator-handoff-contract.md`
- status CLI entrypoint: `scripts/send_supervisor_status_update.py`
- goal completion CLI entrypoint: `scripts/send_supervisor_goal_completion.py`
- baseline delivery CLIs:
  - `scripts/send_operator_message.py`
  - `scripts/send_goal_completion_notification.py`

## Status Update Command (Dry Run)
```bash
RUN_ID="supervisor-status-$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="/tmp/monday-supervisor-status-$RUN_ID"
mkdir -p "$OUT_DIR"

cat >"$OUT_DIR/operator-report.json" <<'JSON'
{
  "run_id": "supervisor-run-123",
  "summary_path": "/tmp/planningops/summary.json",
  "cycle_report_path": "/tmp/planningops/cycle-01/cycle-report.json",
  "status": "review_required",
  "headline": "Supervisor found a promotable successor goal.",
  "operator_action": "review_goal_promotion",
  "goal_key": "uap-goal-driven-autonomy-wave3",
  "message_class_hint": "decision_request",
  "handoff_contract_ref": "planningops/contracts/supervisor-operator-handoff-contract.md",
  "primary_operator_channel": {
    "kind": "slack_skill_cli",
    "transport": "skill"
  }
}
JSON

cat >"$OUT_DIR/inbox-payload.json" <<'JSON'
{
  "title": "Supervisor needs review",
  "status": "review_required",
  "headline": "Supervisor found a promotable successor goal.",
  "operator_action": "review_goal_promotion",
  "recommended_wait_minutes": 0,
  "retry_mode": "none",
  "needs_human_attention": true,
  "attachments": [
    "/tmp/planningops/operator-summary.md",
    "/tmp/planningops/summary.json"
  ],
  "body_markdown": "# Supervisor Operator Summary\n\nReview promotion path.",
  "goal_key": "uap-goal-driven-autonomy-wave3",
  "message_class_hint": "decision_request",
  "handoff_contract_ref": "planningops/contracts/supervisor-operator-handoff-contract.md"
}
JSON

python3 scripts/send_supervisor_status_update.py \
  --operator-report-file "$OUT_DIR/operator-report.json" \
  --inbox-payload-file "$OUT_DIR/inbox-payload.json" \
  --delivery-target "slack://monday/thread-123" \
  --thread-ref "thread-123" \
  --output "$OUT_DIR/supervisor-status-update-report.json"
```

## Goal Completion Command (Dry Run)
```bash
RUN_ID="supervisor-goal-completion-$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="/tmp/monday-supervisor-goal-completion-$RUN_ID"
mkdir -p "$OUT_DIR"

cat >"$OUT_DIR/operator-report.json" <<'JSON'
{
  "run_id": "supervisor-run-456",
  "summary_path": "/tmp/planningops/summary.json",
  "status": "ok",
  "headline": "Supervisor completed the active goal and stopped cleanly.",
  "operator_action": "notify_goal_completion",
  "goal_key": "uap-goal-driven-autonomy-wave3",
  "message_class_hint": "goal_completed",
  "handoff_contract_ref": "planningops/contracts/supervisor-operator-handoff-contract.md",
  "goal_transition_report_path": "/tmp/planningops/goal-transition-report.json",
  "terminal_notification_channel": {
    "kind": "email_cli",
    "transport": "cli"
  }
}
JSON

cat >"$OUT_DIR/operator-summary.md" <<'MD'
# Supervisor Operator Summary

Goal completed cleanly.
MD

cat >"$OUT_DIR/goal-transition-report.json" <<'JSON'
{
  "generated_at_utc": "2026-03-14T04:00:00Z",
  "goal_key": "uap-goal-driven-autonomy-wave3",
  "to_status": "achieved",
  "goal_transition_kind": "terminal_completion",
  "verdict": "pass"
}
JSON

python3 scripts/send_supervisor_goal_completion.py \
  --operator-report-file "$OUT_DIR/operator-report.json" \
  --operator-summary-file "$OUT_DIR/operator-summary.md" \
  --goal-transition-report-file "$OUT_DIR/goal-transition-report.json" \
  --delivery-target "mailto:operator@example.com" \
  --output "$OUT_DIR/supervisor-goal-completion-report.json"
```

## Apply Gate
`apply` mode is expected to stay blocked until real Slack/email transports are wired behind monday-owned CLI or MCP adapters.

Status path:
```bash
python3 scripts/send_supervisor_status_update.py \
  --operator-report-file "$OUT_DIR/operator-report.json" \
  --inbox-payload-file "$OUT_DIR/inbox-payload.json" \
  --delivery-target "slack://monday/thread-123" \
  --mode apply \
  --output "$OUT_DIR/supervisor-status-update-apply-report.json"
```

Goal completion path:
```bash
python3 scripts/send_supervisor_goal_completion.py \
  --operator-report-file "$OUT_DIR/operator-report.json" \
  --operator-summary-file "$OUT_DIR/operator-summary.md" \
  --goal-transition-report-file "$OUT_DIR/goal-transition-report.json" \
  --delivery-target "mailto:operator@example.com" \
  --mode apply \
  --output "$OUT_DIR/supervisor-goal-completion-apply-report.json"
```

Expected gate signals:
- status apply exits non-zero with `operator_transport_not_configured`
- goal completion apply exits non-zero with `goal_completion_transport_not_configured`
- both reports stay `deliveryVerdict=blocked`

## Skill Boundary
- planningops must only emit `operator-report.json`, `operator-summary.md`, `inbox-payload.json`, and optional `goal-transition-report.json`
- monday skills should call:
  - `scripts/send_supervisor_status_update.py`
  - `scripts/send_supervisor_goal_completion.py`
- transport-specific Slack/email behavior must stay behind monday-owned CLI or MCP adapters
- operator-facing skills must not rebuild payload semantics from prompt-local reasoning

## Generated Artifacts
- `$OUT_DIR/supervisor-status-update-report.json`
- `$OUT_DIR/supervisor-status-update-apply-report.json`
- `$OUT_DIR/supervisor-goal-completion-report.json`
- `$OUT_DIR/supervisor-goal-completion-apply-report.json`

## Healthy Signals
- status dry-run report has `verdict=pass`
- status dry-run report has `messageClass=decision_request|status_update|blocked_report`
- status dry-run report has `channelKind=slack_skill_cli` or `channelKind=slack_skill_mcp`
- goal completion dry-run report has `verdict=pass`
- goal completion dry-run report has `messageClass=goal_completed`
- goal completion dry-run report has `channelKind=email_cli` or `channelKind=email_mcp`
- apply gates fail closed with `deliveryVerdict=blocked`

## Rollback Trigger
Trigger rollback if one of:
1. monday wrappers stop requiring `planningops/contracts/supervisor-operator-handoff-contract.md`
2. status delivery no longer respects `primary_operator_channel`
3. goal completion delivery no longer respects `terminal_notification_channel`
4. apply mode succeeds without reviewed transport implementation

Immediate action:
- stop supervisor handoff rollout
- preserve `$OUT_DIR` evidence
- open a follow-up issue with `supervisor_handoff_contract_regression`
