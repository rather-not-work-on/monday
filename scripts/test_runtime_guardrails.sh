#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

RUN_ID="runtime-guard-$(date -u +%Y%m%dT%H%M%SZ)"

python3 "$ROOT_DIR/scripts/validate_runbook_contract.py" \
  --contract "$ROOT_DIR/config/runtime-integration-runbook-contract.json" \
  --output "$TMP_DIR/runtime-integration-runbook-validation.json"

python3 "$ROOT_DIR/scripts/validate_runbook_contract.py" \
  --contract "$ROOT_DIR/config/goal-completion-notifier-runbook-contract.json" \
  --output "$TMP_DIR/goal-completion-notifier-runbook-validation.json"

python3 "$ROOT_DIR/scripts/validate_runbook_contract.py" \
  --contract "$ROOT_DIR/config/operator-channel-adapter-runbook-contract.json" \
  --output "$TMP_DIR/operator-channel-adapter-runbook-validation.json"

python3 "$ROOT_DIR/scripts/validate_runbook_contract.py" \
  --contract "$ROOT_DIR/config/planningops-supervisor-handoff-runbook-contract.json" \
  --output "$TMP_DIR/planningops-supervisor-handoff-runbook-validation.json"

python3 "$ROOT_DIR/scripts/integrate_planningops_handoff.py" \
  --run-id "$RUN_ID" \
  --handoff-report "$TMP_DIR/handoff-smoke-report.json" \
  --queue-out "$TMP_DIR/queue.from-planningops.json" \
  --scheduler-report "$TMP_DIR/scheduler-run-report.json" \
  --integration-report "$TMP_DIR/planningops-handoff-report.json" \
  --idempotency "$TMP_DIR/idempotency.json" \
  --transition-log "$TMP_DIR/scheduler.ndjson"

python3 "$ROOT_DIR/scripts/validate_runtime_evidence.py" \
  --kind scheduler \
  --report "$TMP_DIR/scheduler-run-report.json" \
  --output "$TMP_DIR/scheduler-validation-report.json"

python3 "$ROOT_DIR/scripts/validate_runtime_evidence.py" \
  --kind integration \
  --report "$TMP_DIR/planningops-handoff-report.json" \
  --output "$TMP_DIR/integration-validation-report.json"

python3 "$ROOT_DIR/scripts/run_scheduled_queue_cycle.py" \
  --queue "$TMP_DIR/queue.from-planningops.json" \
  --run-id "${RUN_ID}-replay" \
  --idempotency "$TMP_DIR/idempotency.json" \
  --report "$TMP_DIR/scheduler-replay-report.json" \
  --transition-log "$TMP_DIR/scheduler.ndjson"

python3 "$ROOT_DIR/scripts/validate_runtime_evidence.py" \
  --kind scheduler \
  --report "$TMP_DIR/scheduler-replay-report.json" \
  --output "$TMP_DIR/scheduler-replay-validation-report.json"

python3 - "$TMP_DIR/planningops-handoff-report.json" "$TMP_DIR/scheduler-run-report.json" "$TMP_DIR/scheduler-replay-report.json" <<'PY'
import json
import sys
from pathlib import Path

integration_report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
scheduler_report = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
replay_report = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))

if integration_report.get("verdict") != "pass":
    raise SystemExit("integration run must pass")
if integration_report.get("reason_code") != "ok":
    raise SystemExit(f"integration reason_code must be ok: {integration_report.get('reason_code')}")

if scheduler_report.get("dequeued_count", 0) < 1:
    raise SystemExit("scheduler run must dequeue at least one card")
if scheduler_report.get("blocked_count", 0) != 0:
    raise SystemExit(f"scheduler run must not block cards: {scheduler_report.get('blocked_count')}")

if replay_report.get("verdict") != "pass":
    raise SystemExit("scheduler replay must pass")
if replay_report.get("reason_code") != "duplicates_detected":
    raise SystemExit(
        f"scheduler replay reason_code must be duplicates_detected: {replay_report.get('reason_code')}"
    )
if replay_report.get("duplicate_count", 0) < 1:
    raise SystemExit("scheduler replay must detect duplicate dequeue")
PY

echo "runtime guardrails regression passed"
