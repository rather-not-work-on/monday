#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

operator_report="$TMP_DIR/operator-report.json"
operator_summary="$TMP_DIR/operator-summary.md"
transition_report="$TMP_DIR/goal-transition-report.json"
dry_run_report="$TMP_DIR/supervisor-goal-completion-report.json"
apply_report="$TMP_DIR/supervisor-goal-completion-apply-report.json"
profiles_config="$TMP_DIR/local-operator-channel-profiles.json"

cat >"$profiles_config" <<JSON
{
  "config_version": 1,
  "profiles": {
    "email_cli": {
      "channel_kind": "email_cli",
      "transport_kind": "local_outbox",
      "outbox_root": "$TMP_DIR/tmp-outbox/email",
      "default_target_name": "terminal-notifications",
      "supports_threads": false
    }
  }
}
JSON

cat >"$operator_report" <<'JSON'
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

cat >"$operator_summary" <<'MD'
# Supervisor Operator Summary

Goal completed cleanly.
MD

cat >"$transition_report" <<'JSON'
{
  "generated_at_utc": "2026-03-14T04:00:00Z",
  "goal_key": "uap-goal-driven-autonomy-wave3",
  "to_status": "achieved",
  "goal_transition_kind": "terminal_completion",
  "verdict": "pass"
}
JSON

python3 "$ROOT_DIR/scripts/send_supervisor_goal_completion.py" \
  --operator-report-file "$operator_report" \
  --operator-summary-file "$operator_summary" \
  --goal-transition-report-file "$transition_report" \
  --delivery-target "mailto:operator@example.com" \
  --output "$dry_run_report"

python3 - <<'PY' "$dry_run_report"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "pass", doc
assert doc["delivery_report"]["deliveryVerdict"] == "dry_run", doc
assert doc["delivery_report"]["channelKind"] == "email_cli", doc
assert doc["payload"]["messageClass"] == "goal_completed", doc
assert doc["payload"]["goalKey"] == "uap-goal-driven-autonomy-wave3", doc
assert doc["payload"]["achievedAtUtc"] == "2026-03-14T04:00:00Z", doc
assert doc["payload"]["metadata"]["goal_transition_report_path"] == sys.argv[1].replace("supervisor-goal-completion-report.json", "goal-transition-report.json"), doc
PY

python3 "$ROOT_DIR/scripts/send_supervisor_goal_completion.py" \
  --operator-report-file "$operator_report" \
  --operator-summary-file "$operator_summary" \
  --goal-transition-report-file "$transition_report" \
  --profiles-config "$profiles_config" \
  --mode apply \
  --output "$apply_report"

python3 - <<'PY' "$apply_report"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "pass", doc
assert doc["delegate_script"] == "scripts/send_goal_completion_notification.py", doc
assert doc["delegate_report"]["delivery_report"]["deliveryVerdict"] == "delivered_local_outbox", doc
assert "tmp-outbox/email/" in doc["delegate_report"]["outbox_message_ref"], doc
assert Path(doc["delegate_report"]["outbox_message_ref"]).exists(), doc
PY

echo "supervisor goal completion cli contract ok"
