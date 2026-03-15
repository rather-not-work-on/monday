#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
TEST_OUTBOX_ROOT="runtime-artifacts/test-local-dispatch-cycle"
trap 'rm -rf "$TMP_DIR" "$ROOT_DIR/$TEST_OUTBOX_ROOT" "$ROOT_DIR/runtime-artifacts/messaging/dispatch-packets" "$ROOT_DIR/runtime-artifacts/messaging/dispatch-acks" "$ROOT_DIR/runtime-artifacts/messaging/dispatch-execution-packets" "$ROOT_DIR/runtime-artifacts/messaging/dispatch-receipts" "$ROOT_DIR/runtime-artifacts/messaging/local-dispatch-cycle-report.json"' EXIT

cd "$ROOT_DIR"

profiles_config="$TMP_DIR/local-operator-channel-profiles.json"
operator_payload="$TMP_DIR/operator-message.json"
operator_report="$TMP_DIR/operator-message-report.json"
dispatch_packet="$ROOT_DIR/runtime-artifacts/messaging/dispatch-packets/wave17-cycle.json"
cycle_report="$TMP_DIR/local-dispatch-cycle-report.json"
cycle_report_repeat="$TMP_DIR/local-dispatch-cycle-repeat-report.json"

rm -rf "$ROOT_DIR/runtime-artifacts/messaging/dispatch-packets" \
       "$ROOT_DIR/runtime-artifacts/messaging/dispatch-acks" \
       "$ROOT_DIR/runtime-artifacts/messaging/dispatch-execution-packets" \
       "$ROOT_DIR/runtime-artifacts/messaging/dispatch-receipts"

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
  "messageClass": "blocked_report",
  "deliveryMode": "apply",
  "goalKey": "uap-goal-driven-autonomy-wave17",
  "body": "run one local dispatch cycle",
  "runId": "run-wave17-q30",
  "taskId": "queue-wave17-q30",
  "target": {
    "channelKind": "slack_skill_cli",
    "threadRef": "thread-wave17-q30"
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

python3 "$ROOT_DIR/scripts/run_local_dispatch_cycle.py" \
  --output "$cycle_report"

python3 - <<'PY' "$cycle_report"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "pass", doc
assert doc["selection_mode"] == "first_ready_packet", doc
assert doc["cycle_status"] == "recorded", doc
assert doc["ack_status"] == "recorded", doc
assert doc["execution_verdict"] == "ready_for_local_bridge", doc
assert doc["selected_dispatch_packet_ref"].startswith("runtime-artifacts/messaging/dispatch-packets/"), doc
assert doc["execution_packet_ref"].startswith("runtime-artifacts/messaging/dispatch-execution-packets/"), doc
assert doc["dispatch_receipt_ref"].startswith("runtime-artifacts/messaging/dispatch-receipts/"), doc
assert doc["ack_checkpoint_ref"].startswith("runtime-artifacts/messaging/dispatch-acks/"), doc
PY

python3 - <<'PY' "$cycle_report"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for key in ["execution_packet_ref", "dispatch_receipt_ref", "ack_checkpoint_ref"]:
    assert Path(doc[key]).exists(), (key, doc)
PY

python3 "$ROOT_DIR/scripts/run_local_dispatch_cycle.py" \
  --dispatch-packet-file "$dispatch_packet" \
  --output "$cycle_report_repeat"

python3 - <<'PY' "$cycle_report_repeat"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "pass", doc
assert doc["selection_mode"] == "explicit_argument", doc
assert doc["cycle_status"] == "already_recorded", doc
assert doc["receipt_status"] == "recorded", doc
assert doc["ack_status"] == "already_recorded", doc
assert doc["execution_verdict"] == "already_dispatched", doc
PY
