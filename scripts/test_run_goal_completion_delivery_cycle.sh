#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
TEST_OUTBOX_ROOT="runtime-artifacts/test-goal-completion-delivery-cycle"
trap 'rm -rf "$TMP_DIR" "$ROOT_DIR/$TEST_OUTBOX_ROOT" "$ROOT_DIR/runtime-artifacts/messaging/delivery-reports" "$ROOT_DIR/runtime-artifacts/messaging/delivery-cycles" "$ROOT_DIR/runtime-artifacts/messaging/dispatch-packets" "$ROOT_DIR/runtime-artifacts/messaging/dispatch-acks" "$ROOT_DIR/runtime-artifacts/messaging/dispatch-execution-packets" "$ROOT_DIR/runtime-artifacts/messaging/dispatch-receipts"' EXIT

cd "$ROOT_DIR"

profiles_config="$TMP_DIR/local-operator-channel-profiles.json"
payload="$TMP_DIR/goal-completion.json"
cycle_report_one="$ROOT_DIR/runtime-artifacts/messaging/delivery-cycles/goal-completion-wave18.json"
cycle_report_two="$ROOT_DIR/runtime-artifacts/messaging/delivery-cycles/goal-completion-wave18-repeat.json"

cat >"$profiles_config" <<JSON
{
  "config_version": 1,
  "profiles": {
    "email_cli": {
      "channel_kind": "email_cli",
      "transport_kind": "local_outbox",
      "outbox_root": "$TEST_OUTBOX_ROOT/email",
      "default_target_name": "terminal-notifications",
      "supports_threads": false
    }
  }
}
JSON

cat >"$payload" <<'JSON'
{
  "messageClass": "goal_completed",
  "deliveryMode": "apply",
  "goalKey": "uap-goal-driven-autonomy-wave18",
  "body": "goal completion delivery cycle",
  "achievedAtUtc": "2026-03-15T00:00:00Z",
  "target": {
    "channelKind": "email_cli"
  }
}
JSON

python3 "$ROOT_DIR/scripts/run_goal_completion_delivery_cycle.py" \
  --payload-file "$payload" \
  --profiles-config "$profiles_config" \
  --output "$cycle_report_one"

python3 - <<'PY' "$cycle_report_one" "$payload"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
payload_path = str(Path(sys.argv[2]).resolve())
assert doc["verdict"] == "pass", doc
assert doc["entrypoint_script"] == "run_goal_completion_delivery_cycle.py", doc
assert doc["source_payload_ref"] == payload_path, doc
assert doc["goal_key"] == "uap-goal-driven-autonomy-wave18", doc
assert doc["message_class"] == "goal_completed", doc
assert doc["channel_kind"] == "email_cli", doc
assert doc["cycle_status"] == "recorded", doc
for key in ["delivery_report_ref", "dispatch_packet_ref", "execution_packet_ref", "ack_checkpoint_ref", "dispatch_receipt_ref", "step_cycle_report_ref"]:
    assert Path(doc[key]).exists(), (key, doc)
PY

python3 "$ROOT_DIR/scripts/run_goal_completion_delivery_cycle.py" \
  --payload-file "$payload" \
  --profiles-config "$profiles_config" \
  --output "$cycle_report_two"

python3 - <<'PY' "$cycle_report_two"
import json
import sys
from pathlib import Path

doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert doc["verdict"] == "pass", doc
assert doc["cycle_status"] == "already_recorded", doc
assert doc["delivery_verdict"] == "delivered_local_outbox", doc
assert doc["dispatch_verdict"] == "already_acknowledged", doc
assert doc["dispatch_receipt_ref"].startswith("runtime-artifacts/messaging/dispatch-receipts/"), doc
PY
