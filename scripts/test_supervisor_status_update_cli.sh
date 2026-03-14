#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

operator_report="$TMP_DIR/operator-report.json"
inbox_payload="$TMP_DIR/inbox-payload.json"
dry_run_report="$TMP_DIR/supervisor-status-update-report.json"
apply_report="$TMP_DIR/supervisor-status-update-apply-report.json"

cat >"$operator_report" <<'JSON'
{
  "run_id": "supervisor-run-123",
  "summary_path": "/tmp/planningops/summary.json",
  "cycle_report_path": "/tmp/planningops/cycle-01/cycle-report.json",
  "status": "review_required",
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

cat >"$inbox_payload" <<'JSON'
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

python3 "$ROOT_DIR/scripts/send_supervisor_status_update.py" \
  --operator-report-file "$operator_report" \
  --inbox-payload-file "$inbox_payload" \
  --delivery-target "slack://monday/thread-123" \
  --thread-ref "thread-123" \
  --output "$dry_run_report"

python3 - <<'PY' "$dry_run_report"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "pass", doc
assert doc["delivery_report"]["deliveryVerdict"] == "dry_run", doc
assert doc["delivery_report"]["channelKind"] == "slack_skill_cli", doc
assert doc["payload"]["messageClass"] == "decision_request", doc
assert doc["payload"]["goalKey"] == "uap-goal-driven-autonomy-wave3", doc
assert doc["payload"]["metadata"]["handoff_contract_ref"] == "planningops/contracts/supervisor-operator-handoff-contract.md", doc
assert doc["payload"]["metadata"]["attachments"][0].endswith("operator-summary.md"), doc
PY

if python3 "$ROOT_DIR/scripts/send_supervisor_status_update.py" \
  --operator-report-file "$operator_report" \
  --inbox-payload-file "$inbox_payload" \
  --delivery-target "slack://monday/thread-123" \
  --mode apply \
  --output "$apply_report"; then
  echo "expected supervisor status update apply baseline to fail without transport"
  exit 1
fi

python3 - <<'PY' "$apply_report"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "fail", doc
assert doc["delivery_report"]["deliveryVerdict"] == "blocked", doc
assert doc["errors"] == ["operator_transport_not_configured"], doc
PY

echo "supervisor status update cli contract ok"
