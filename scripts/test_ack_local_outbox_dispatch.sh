#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
TEST_OUTBOX_ROOT="runtime-artifacts/test-local-outbox-ack"
trap 'rm -rf "$TMP_DIR" "$ROOT_DIR/$TEST_OUTBOX_ROOT" "$ROOT_DIR/runtime-artifacts/messaging/dispatch-acks"' EXIT

cd "$ROOT_DIR"

profiles_config="$TMP_DIR/local-operator-channel-profiles.json"
operator_payload="$TMP_DIR/operator-message.json"
operator_report="$TMP_DIR/operator-message-report.json"
dispatch_packet="$TMP_DIR/dispatch-packet.json"
ack_report_one="$TMP_DIR/dispatch-ack-one.json"
ack_report_two="$TMP_DIR/dispatch-ack-two.json"

cat >"$profiles_config" <<JSON
{
  "config_version": 1,
  "profiles": {
    "slack_skill_cli": {
      "channel_kind": "slack_skill_cli",
      "transport_kind": "local_outbox",
      "outbox_root": "$TEST_OUTBOX_ROOT/slack",
      "default_target_name": "monday-operator",
      "supports_threads": true
    }
  }
}
JSON

cat >"$operator_payload" <<'JSON'
{
  "messageClass": "decision_request",
  "deliveryMode": "apply",
  "goalKey": "uap-goal-driven-autonomy-wave16",
  "body": "ack this dispatch packet",
  "runId": "run-wave16-002",
  "taskId": "queue-wave16-002",
  "target": {
    "channelKind": "slack_skill_cli",
    "threadRef": "thread-wave16-ack"
  }
}
JSON

python3 "$ROOT_DIR/scripts/send_operator_message.py" \
  --payload-file "$operator_payload" \
  --profiles-config "$profiles_config" \
  --mode apply \
  --output "$operator_report"

python3 "$ROOT_DIR/scripts/export_local_outbox_dispatch_packet.py" \
  --delivery-report-file "$operator_report" \
  --output "$dispatch_packet"

python3 "$ROOT_DIR/scripts/ack_local_outbox_dispatch.py" \
  --dispatch-packet-file "$dispatch_packet" \
  --output "$ack_report_one"

python3 - <<'PY' "$ack_report_one"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "pass", doc
assert doc["ack_status"] == "recorded", doc
assert doc["ack_reason"] == "dispatch_consumed_by_local_skill_boundary", doc
checkpoint_ref = doc["ack_checkpoint_ref"]
assert checkpoint_ref.startswith("runtime-artifacts/messaging/dispatch-acks/"), doc
checkpoint = doc["ack_checkpoint"]
assert checkpoint["ack_status"] == "recorded", doc
assert checkpoint["dispatch_packet_ref"].endswith("dispatch-packet.json"), doc
PY

python3 "$ROOT_DIR/scripts/ack_local_outbox_dispatch.py" \
  --dispatch-packet-file "$dispatch_packet" \
  --output "$ack_report_two"

python3 - <<'PY' "$ack_report_two"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "pass", doc
assert doc["ack_status"] == "already_recorded", doc
assert doc["ack_checkpoint"]["ack_status"] == "recorded", doc
assert doc["ack_checkpoint_ref"].startswith("runtime-artifacts/messaging/dispatch-acks/"), doc
PY
