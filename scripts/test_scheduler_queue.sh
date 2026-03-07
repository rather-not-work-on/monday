#!/usr/bin/env bash
set -euo pipefail

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

python3 scripts/scheduler_queue.py \
  --run-id test-run-1 \
  --idempotency "$TMP_DIR/idempotency.json" \
  --report "$TMP_DIR/run-report-first.json" \
  --transition-log "$TMP_DIR/scheduler.ndjson"
python3 scripts/validate_runtime_evidence.py \
  --kind scheduler \
  --report "$TMP_DIR/run-report-first.json" \
  --output "$TMP_DIR/runtime-scheduler-first-validation.json"
python3 scripts/scheduler_queue.py \
  --run-id test-run-2 \
  --idempotency "$TMP_DIR/idempotency.json" \
  --report "$TMP_DIR/run-report-second.json" \
  --transition-log "$TMP_DIR/scheduler.ndjson"
python3 scripts/validate_runtime_evidence.py \
  --kind scheduler \
  --report "$TMP_DIR/run-report-second.json" \
  --output "$TMP_DIR/runtime-scheduler-second-validation.json"

first_dequeued=$(jq -r '.dequeued_count' "$TMP_DIR/run-report-first.json")
second_duplicate=$(jq -r '.duplicate_count' "$TMP_DIR/run-report-second.json")
first_reason_code=$(jq -r '.reason_code' "$TMP_DIR/run-report-first.json")

if [[ "$first_dequeued" -lt 1 ]]; then
  echo "expected first run to dequeue at least one card"
  exit 1
fi

if [[ "$first_reason_code" != "blocked_dependencies" ]]; then
  echo "expected first run reason_code to reflect blocked dependencies"
  exit 1
fi

if [[ "$second_duplicate" -lt 1 ]]; then
  echo "expected second run to detect duplicate dequeue"
  exit 1
fi

echo "scheduler queue test passed"
