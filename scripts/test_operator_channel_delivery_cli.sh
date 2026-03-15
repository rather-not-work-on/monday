#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

operator_payload="$TMP_DIR/operator-message.json"
operator_report="$TMP_DIR/operator-message-report.json"
operator_apply_report="$TMP_DIR/operator-message-apply-report.json"
operator_local_payload="$TMP_DIR/operator-message-local.json"
operator_local_dry_run_report="$TMP_DIR/operator-message-local-dry-run-report.json"
operator_local_apply_report="$TMP_DIR/operator-message-local-apply-report.json"
completion_payload="$TMP_DIR/goal-completion.json"
completion_report="$TMP_DIR/goal-completion-report.json"
completion_apply_report="$TMP_DIR/goal-completion-apply-report.json"
completion_local_payload="$TMP_DIR/goal-completion-local.json"
completion_local_dry_run_report="$TMP_DIR/goal-completion-local-dry-run-report.json"
completion_local_apply_report="$TMP_DIR/goal-completion-local-apply-report.json"
profiles_config="$TMP_DIR/local-operator-channel-profiles.json"

cat >"$profiles_config" <<JSON
{
  "config_version": 1,
  "profiles": {
    "slack_skill_cli": {
      "channel_kind": "slack_skill_cli",
      "transport_kind": "local_outbox",
      "outbox_root": "$TMP_DIR/tmp-outbox/slack",
      "default_target_name": "monday-operator",
      "supports_threads": true
    },
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

cat >"$operator_local_payload" <<'JSON'
{
  "messageClass": "decision_request",
  "deliveryMode": "dry-run",
  "goalKey": "uap-goal-driven-autonomy-wave15",
  "body": "operator update via local profile",
  "runId": "run-456",
  "target": {
    "channelKind": "slack_skill_cli",
    "threadRef": "thread-local"
  }
}
JSON

python3 "$ROOT_DIR/scripts/send_operator_message.py" \
  --payload-file "$operator_local_payload" \
  --profiles-config "$profiles_config" \
  --output "$operator_local_dry_run_report"

python3 - <<'PY' "$operator_local_dry_run_report"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "pass", doc
assert doc["target_resolution_mode"] == "local_profile", doc
assert doc["delivery_report"]["deliveryVerdict"] == "dry_run", doc
assert doc["delivery_report"]["targetProfileRef"].endswith("#/profiles/slack_skill_cli"), doc
assert doc["payload"]["target"]["deliveryTarget"] == "local-outbox://monday-operator", doc
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

python3 "$ROOT_DIR/scripts/send_operator_message.py" \
  --payload-file "$operator_local_payload" \
  --profiles-config "$profiles_config" \
  --mode apply \
  --output "$operator_local_apply_report"

python3 - <<'PY' "$operator_local_apply_report"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "pass", doc
assert doc["delivery_report"]["deliveryVerdict"] == "delivered_local_outbox", doc
assert "tmp-outbox/slack/" in doc["outbox_message_ref"], doc
assert Path(doc["outbox_message_ref"]).exists(), doc
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

cat >"$completion_local_payload" <<'JSON'
{
  "messageClass": "goal_completed",
  "deliveryMode": "dry-run",
  "goalKey": "uap-goal-driven-autonomy-wave15",
  "body": "goal completed through local profile",
  "achievedAtUtc": "2026-03-15T00:00:00Z",
  "target": {
    "channelKind": "email_cli"
  }
}
JSON

python3 "$ROOT_DIR/scripts/send_goal_completion_notification.py" \
  --payload-file "$completion_local_payload" \
  --profiles-config "$profiles_config" \
  --output "$completion_local_dry_run_report"

python3 - <<'PY' "$completion_local_dry_run_report"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "pass", doc
assert doc["target_resolution_mode"] == "local_profile", doc
assert doc["delivery_report"]["deliveryVerdict"] == "dry_run", doc
assert doc["delivery_report"]["targetProfileRef"].endswith("#/profiles/email_cli"), doc
assert doc["payload"]["target"]["deliveryTarget"] == "local-outbox://terminal-notifications", doc
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

python3 "$ROOT_DIR/scripts/send_goal_completion_notification.py" \
  --payload-file "$completion_local_payload" \
  --profiles-config "$profiles_config" \
  --mode apply \
  --output "$completion_local_apply_report"

python3 - <<'PY' "$completion_local_apply_report"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "pass", doc
assert doc["delivery_report"]["deliveryVerdict"] == "delivered_local_outbox", doc
assert "tmp-outbox/email/" in doc["outbox_message_ref"], doc
assert Path(doc["outbox_message_ref"]).exists(), doc
PY

echo "operator channel delivery cli contract ok"
