#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

operator_payload="$TMP_DIR/operator-message.json"
operator_report="$TMP_DIR/operator-message-report.json"
operator_apply_report="$TMP_DIR/operator-message-apply-report.json"
completion_payload="$TMP_DIR/goal-completion.json"
completion_report="$TMP_DIR/goal-completion-report.json"
completion_apply_report="$TMP_DIR/goal-completion-apply-report.json"

cat >"$operator_payload" <<'JSON'
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

python3 "$ROOT_DIR/scripts/send_operator_message.py" \
  --payload-file "$operator_payload" \
  --output "$operator_report"

python3 - <<'PY' "$operator_report"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "pass", doc
assert doc["delivery_report"]["deliveryVerdict"] == "dry_run", doc
assert doc["delivery_report"]["channelKind"] == "slack_skill_cli", doc
PY

if python3 "$ROOT_DIR/scripts/send_operator_message.py" \
  --payload-file "$operator_payload" \
  --mode apply \
  --output "$operator_apply_report"; then
  echo "expected operator apply baseline to fail without transport"
  exit 1
fi

python3 - <<'PY' "$operator_apply_report"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "fail", doc
assert doc["delivery_report"]["deliveryVerdict"] == "blocked", doc
PY

cat >"$completion_payload" <<'JSON'
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

python3 "$ROOT_DIR/scripts/send_goal_completion_notification.py" \
  --payload-file "$completion_payload" \
  --output "$completion_report"

python3 - <<'PY' "$completion_report"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "pass", doc
assert doc["delivery_report"]["deliveryVerdict"] == "dry_run", doc
assert doc["delivery_report"]["channelKind"] == "email_cli", doc
PY

if python3 "$ROOT_DIR/scripts/send_goal_completion_notification.py" \
  --payload-file "$completion_payload" \
  --mode apply \
  --output "$completion_apply_report"; then
  echo "expected completion apply baseline to fail without transport"
  exit 1
fi

python3 - <<'PY' "$completion_apply_report"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "fail", doc
assert doc["delivery_report"]["deliveryVerdict"] == "blocked", doc
PY

echo "operator channel delivery cli contract ok"
