#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cd "$ROOT_DIR"

PLANNINGOPS_DIR="$TMP_DIR/platform-planningops"
QUEUE_DIR="$PLANNINGOPS_DIR/runtime-artifacts/scheduler"
DB_PATH="$TMP_DIR/runtime-queue.sqlite3"
PACKET_PATH="$TMP_DIR/admission-packet.json"
REPORT_PATH="$TMP_DIR/admission-report.json"

mkdir -p "$QUEUE_DIR"
cp fixtures/runtime-scheduler-queue.sample.json "$QUEUE_DIR/queue-seed.json"

cat > "$PACKET_PATH" <<'JSON'
{
  "admission_version": 1,
  "generated_at_utc": "2026-03-15T00:00:00Z",
  "admission_contract_ref": "planningops/contracts/scheduled-queue-admission-handoff-contract.md",
  "source_repo": "rather-not-work-on/platform-planningops",
  "goal_key": "uap-goal-driven-autonomy-wave4",
  "schedule_key": "local-tick-5m",
  "queue_seed_ref": "runtime-artifacts/scheduler/queue-seed.json",
  "seed_format": "runtime_scheduler_queue_items_json",
  "seed_item_count": 2,
  "verdict": "pass"
}
JSON

python3 scripts/admit_scheduled_queue_packet.py \
  --packet "$PACKET_PATH" \
  --planningops-repo-dir "$PLANNINGOPS_DIR" \
  --queue-db "$DB_PATH" \
  --replace-existing \
  --output "$REPORT_PATH"

python3 - "$REPORT_PATH" "$DB_PATH" <<'PY'
import json
import sqlite3
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text())
if report["verdict"] != "pass":
    raise SystemExit(f"expected verdict=pass, got {report['verdict']}")
if report["admitted_count"] != 2:
    raise SystemExit(f"expected admitted_count=2, got {report['admitted_count']}")
if report["goal_key"] != "uap-goal-driven-autonomy-wave4":
    raise SystemExit(f"unexpected goal_key: {report['goal_key']}")

conn = sqlite3.connect(sys.argv[2])
count = conn.execute("SELECT COUNT(*) FROM queue_items").fetchone()[0]
conn.close()
if count != 2:
    raise SystemExit(f"expected 2 queue rows, got {count}")
PY

echo "scheduled queue admission packet test passed"
