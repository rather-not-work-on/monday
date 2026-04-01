#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cd "$ROOT_DIR"

planningops_validation="$TMP_DIR/platform-planningops/planningops/artifacts/validation"
mkdir -p "$planningops_validation"

day_packet_path="$planningops_validation/monday-local-operator-day-packet.json"
mission_packet_path="$planningops_validation/monday-local-mission-packet.json"
handoff_report_path="$planningops_validation/operator-handoff-report.json"
local_operator_report_path="$planningops_validation/monday-local-operator-stack-report.json"
ready_bridge_path="$planningops_validation/monday-local-operator-inbox-payload-ready.json"
blocked_bridge_path="$planningops_validation/monday-local-operator-inbox-payload-blocked.json"
output_root="$TMP_DIR/runtime-artifacts/integration/planningops-local-operator-inbox"
dry_report="$TMP_DIR/consumer-dry-run.json"
blocked_report="$TMP_DIR/consumer-apply-blocked.json"

cat >"$mission_packet_path" <<'JSON'
{
  "generated_at_utc": "2026-04-01T10:00:00Z",
  "packet_id": "monday-local-mission-20260401T100000Z",
  "contract_ref": "planningops/contracts/monday-local-mission-packet-contract.md",
  "artifact_paths": {
    "latest_packet_path": "/tmp/latest-mission.json",
    "stamped_packet_path": "/tmp/stamped-mission.json",
    "output_path": null
  },
  "mission_packet": {
    "version": "v1",
    "packet_id": "monday-local-mission-20260401T100000Z",
    "mission_objective": "Resolve the next local monday runtime launch.",
    "mission_prompt": "Launch monday locally through the deterministic packet path.",
    "planner_profile": "local_ollama",
    "launch_mode": "direct",
    "local_model_route": "direct_local_ollama",
    "source_kind": "latest",
    "primary_action": "Launch the local monday runtime.",
    "preflight_command": "python3 planningops/scripts/run_monday_local_operator_stack.py --execution-mode direct --direct-profile local_ollama --probe-endpoints on --run-id monday-local-mission-20260401T100000Z",
    "monday_runtime_entrypoint_command": "cd ../monday && python3 scripts/run_local_runtime_smoke.py --profile local_ollama --run-id monday-local-mission-20260401T100000Z",
    "rollback_command": "cd ../platform-provider-gateway && bash scripts/litellm_stack_launcher.sh --mode start",
    "expected_evidence_outputs": [],
    "immediate_actions": [
      "Run the monday local runtime smoke."
    ],
    "target_lines": [
      "monday local runtime smoke"
    ],
    "local_validation_snapshot_status": "present",
    "local_validation_records": [],
    "local_validation_summary_lines": [
      "monday_local_operator_stack_report: freshness=fresh promotability=promotable"
    ],
    "local_validation_action_lines": [],
    "source_artifacts": {
      "handoff_report_path": "/tmp/handoff.json",
      "local_operator_report_path": "/tmp/operator.json"
    }
  }
}
JSON

cat >"$day_packet_path" <<JSON
{
  "generated_at_utc": "2026-04-01T10:05:00Z",
  "day_packet_id": "monday-local-day-20260401T100500Z",
  "contract_ref": "planningops/contracts/monday-local-operator-day-packet-contract.md",
  "artifact_paths": {
    "latest_packet_path": "$day_packet_path",
    "stamped_packet_path": "$TMP_DIR/stamped-day.json",
    "output_path": null
  },
  "day_packet": {
    "version": "v1",
    "day_packet_id": "monday-local-day-20260401T100500Z",
    "mission_packet_id": "monday-local-mission-20260401T100000Z",
    "headline": "Monday local operator day packet: Resolve the next local monday runtime launch.",
    "mission_objective": "Resolve the next local monday runtime launch.",
    "mission_prompt": "Launch monday locally through the deterministic packet path.",
    "planner_profile": "local_ollama",
    "launch_mode": "direct",
    "local_model_route": "direct_local_ollama",
    "first_action_command": "python3 planningops/scripts/run_monday_local_operator_stack.py --execution-mode direct --direct-profile local_ollama --probe-endpoints on --run-id monday-local-mission-20260401T100000Z",
    "monday_runtime_entrypoint_command": "cd ../monday && python3 scripts/run_local_runtime_smoke.py --profile local_ollama --run-id monday-local-mission-20260401T100000Z",
    "rollback_command": "cd ../platform-provider-gateway && bash scripts/litellm_stack_launcher.sh --mode start",
    "queue_lines": [],
    "target_lines": [
      "monday local runtime smoke"
    ],
    "immediate_actions": [
      "Run the monday local runtime smoke."
    ],
    "local_validation_snapshot_status": "present",
    "local_validation_records": [],
    "local_validation_summary_lines": [
      "monday_local_operator_stack_report: freshness=fresh promotability=promotable"
    ],
    "local_validation_action_lines": [],
    "attachments": [
      "$day_packet_path"
    ],
    "body_markdown": "## Monday Local Operator Day Packet",
    "source_artifacts": {
      "mission_packet_path": "$mission_packet_path",
      "handoff_report_path": "$handoff_report_path",
      "local_operator_report_path": "$local_operator_report_path"
    }
  }
}
JSON

cat >"$handoff_report_path" <<'JSON'
{
  "record": {
    "headline": "Launch monday locally.",
    "source_kind": "latest",
    "target_lines": [
      "monday local runtime smoke"
    ],
    "immediate_action_lines": [
      "Run the monday local runtime smoke."
    ]
  }
}
JSON

cat >"$local_operator_report_path" <<'JSON'
{
  "readiness": {
    "status": "ready"
  },
  "direct_profile": "local_ollama"
}
JSON

cat >"$ready_bridge_path" <<JSON
{
  "generated_at_utc": "2026-04-01T10:10:00Z",
  "bridge_id": "monday-local-inbox-20260401T101000Z",
  "contract_ref": "planningops/contracts/monday-local-operator-inbox-payload-bridge-contract.md",
  "artifact_paths": {
    "latest_payload_path": "$ready_bridge_path",
    "stamped_payload_path": "$TMP_DIR/stamped-ready-bridge.json",
    "output_path": null
  },
  "payload": {
    "title": "Monday local operator day packet: Resolve the next local monday runtime launch.",
    "status": "ready",
    "headline": "Monday local operator day packet: Resolve the next local monday runtime launch.",
    "priority_headline": "Monday local operator day packet: Resolve the next local monday runtime launch.",
    "operator_action": "launch_monday_local_runtime",
    "recommended_wait_minutes": 0,
    "retry_mode": "none",
    "needs_human_attention": false,
    "message_class_hint": "status_update",
    "planner_profile": "local_ollama",
    "launch_mode": "direct",
    "local_model_route": "direct_local_ollama",
    "day_packet_id": "monday-local-day-20260401T100500Z",
    "mission_packet_id": "monday-local-mission-20260401T100000Z",
    "mission_objective": "Resolve the next local monday runtime launch.",
    "first_action_command": "python3 planningops/scripts/run_monday_local_operator_stack.py --execution-mode direct --direct-profile local_ollama --probe-endpoints on --run-id monday-local-mission-20260401T100000Z",
    "monday_runtime_entrypoint_command": "cd ../monday && python3 scripts/run_local_runtime_smoke.py --profile local_ollama --run-id monday-local-mission-20260401T100000Z",
    "rollback_command": "cd ../platform-provider-gateway && bash scripts/litellm_stack_launcher.sh --mode start",
    "local_validation_snapshot_status": "present",
    "local_validation_summary_lines": [
      "monday_local_operator_stack_report: freshness=fresh promotability=promotable"
    ],
    "local_validation_action_lines": [],
    "queue_lines": [],
    "target_lines": [
      "monday local runtime smoke"
    ],
    "immediate_actions": [
      "Run the monday local runtime smoke."
    ],
    "attachments": [
      "$ready_bridge_path",
      "$day_packet_path"
    ],
    "body_markdown": "## Monday Local Operator Inbox Payload",
    "bridge_contract_ref": "planningops/contracts/monday-local-operator-inbox-payload-bridge-contract.md",
    "source_artifacts": {
      "day_packet_path": "$day_packet_path",
      "mission_packet_path": "$mission_packet_path",
      "handoff_report_path": "$handoff_report_path",
      "local_operator_report_path": "$local_operator_report_path"
    }
  }
}
JSON

cat >"$blocked_bridge_path" <<JSON
{
  "generated_at_utc": "2026-04-01T10:15:00Z",
  "bridge_id": "monday-local-inbox-20260401T101500Z",
  "contract_ref": "planningops/contracts/monday-local-operator-inbox-payload-bridge-contract.md",
  "artifact_paths": {
    "latest_payload_path": "$blocked_bridge_path",
    "stamped_payload_path": "$TMP_DIR/stamped-blocked-bridge.json",
    "output_path": null
  },
  "payload": {
    "title": "Monday local operator day packet: Resolve the next local monday runtime launch.",
    "status": "blocked",
    "headline": "Monday local operator day packet: Resolve the next local monday runtime launch.",
    "priority_headline": "Monday local operator day packet: Resolve the next local monday runtime launch.",
    "operator_action": "launch_monday_local_runtime",
    "recommended_wait_minutes": 5,
    "retry_mode": "manual_recheck",
    "needs_human_attention": true,
    "message_class_hint": "decision_request",
    "planner_profile": "local_ollama",
    "launch_mode": "direct",
    "local_model_route": "direct_local_ollama",
    "day_packet_id": "monday-local-day-20260401T100500Z",
    "mission_packet_id": "monday-local-mission-20260401T100000Z",
    "mission_objective": "Resolve the next local monday runtime launch.",
    "first_action_command": "python3 planningops/scripts/run_monday_local_operator_stack.py --execution-mode direct --direct-profile local_ollama --probe-endpoints on --run-id monday-local-mission-20260401T100000Z",
    "monday_runtime_entrypoint_command": "cd ../monday && python3 scripts/run_local_runtime_smoke.py --profile local_ollama --run-id monday-local-mission-20260401T100000Z",
    "rollback_command": "cd ../platform-provider-gateway && bash scripts/litellm_stack_launcher.sh --mode start",
    "local_validation_snapshot_status": "present",
    "local_validation_summary_lines": [
      "monday_local_operator_stack_report: freshness=stale promotability=blocked"
    ],
    "local_validation_action_lines": [
      "refresh the promoted local operator stack report first"
    ],
    "queue_lines": [],
    "target_lines": [
      "monday local runtime smoke"
    ],
    "immediate_actions": [
      "Run the monday local runtime smoke."
    ],
    "attachments": [
      "$blocked_bridge_path",
      "$day_packet_path"
    ],
    "body_markdown": "## Monday Local Operator Inbox Payload",
    "bridge_contract_ref": "planningops/contracts/monday-local-operator-inbox-payload-bridge-contract.md",
    "source_artifacts": {
      "day_packet_path": "$day_packet_path",
      "mission_packet_path": "$mission_packet_path",
      "handoff_report_path": "$handoff_report_path",
      "local_operator_report_path": "$local_operator_report_path"
    }
  }
}
JSON

python3 "$ROOT_DIR/scripts/consume_planningops_local_operator_inbox_payload.py" \
  --inbox-payload-file "$ready_bridge_path" \
  --run-id "test-planningops-local-inbox-consumer" \
  --output-root "$output_root" \
  --output "$dry_report"

python3 - <<'PY' "$dry_report" "$output_root"
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
output_root = Path(sys.argv[2])
launch_request_path = output_root / "test-planningops-local-inbox-consumer" / "launch-request.json"
mission_file_path = output_root / "test-planningops-local-inbox-consumer" / "mission.json"

assert report["verdict"] == "pass", report
assert report["reason_code"] == "dry_run", report
assert report["consumer_status"] == "ready_to_launch", report
assert report["bridge_id"] == "monday-local-inbox-20260401T101000Z", report
assert report["launch_request"]["can_launch"] is True, report
assert report["launch_request"]["block_reasons"] == [], report
assert report["launch_request"]["planner_profile"] == "local_ollama", report
assert report["launch_request"]["launch_mode"] == "direct", report
assert report["launch_request"]["local_model_route"] == "direct_local_ollama", report
assert report["launch_request"]["source_day_packet_id"] == "monday-local-day-20260401T100500Z", report
assert report["launch_request"]["source_mission_packet_id"] == "monday-local-mission-20260401T100000Z", report
assert report["launch_request"]["runtime_command_args"] == [
    "python3",
    "scripts/run_local_runtime_smoke.py",
    "--profile",
    "local_ollama",
    "--mission-file",
    str(mission_file_path.resolve()),
    "--run-id",
    "monday-local-inbox-20260401T101000Z",
    "--output",
    str((output_root / "test-planningops-local-inbox-consumer" / "local-runtime-smoke.json").resolve()),
], report
assert launch_request_path.exists(), launch_request_path
mission_file = json.loads(mission_file_path.read_text(encoding="utf-8"))
assert mission_file == {
    "missionId": "monday-local-mission-20260401T100000Z",
    "objective": "Resolve the next local monday runtime launch.",
}, mission_file
contract_text = Path("contracts/planningops-local-operator-inbox-consumer-contract.md").read_text(encoding="utf-8")
assert "launch_request" in contract_text, contract_text
assert "runtime_command_args" in contract_text, contract_text
PY

python3 "$ROOT_DIR/scripts/consume_planningops_local_operator_inbox_payload.py" \
  --inbox-payload-file "$blocked_bridge_path" \
  --run-id "test-planningops-local-inbox-consumer-blocked" \
  --mode apply \
  --output-root "$output_root" \
  --output "$blocked_report"

python3 - <<'PY' "$blocked_report"
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

assert report["verdict"] == "blocked", report
assert report["reason_code"] == "launch_blocked", report
assert report["consumer_status"] == "blocked", report
assert report["launch_request"]["can_launch"] is False, report
assert report["launch_request"]["block_reasons"] == [
    "payload_status=blocked",
    "needs_human_attention",
    "local_validation_actions_present",
], report
assert report["execution"]["attempted"] is False, report
PY

echo "planningops local operator inbox consumer contract ok"
