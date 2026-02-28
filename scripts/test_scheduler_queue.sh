#!/usr/bin/env bash
set -euo pipefail

rm -f artifacts/scheduler/idempotency.json artifacts/scheduler/run-report-first.json artifacts/scheduler/run-report-second.json artifacts/transition-log/scheduler.ndjson

python3 scripts/scheduler_queue.py --run-id test-run-1 --report artifacts/scheduler/run-report-first.json
python3 scripts/scheduler_queue.py --run-id test-run-2 --report artifacts/scheduler/run-report-second.json

first_dequeued=$(jq -r '.dequeued_count' artifacts/scheduler/run-report-first.json)
second_duplicate=$(jq -r '.duplicate_count' artifacts/scheduler/run-report-second.json)

if [[ "$first_dequeued" -lt 1 ]]; then
  echo "expected first run to dequeue at least one card"
  exit 1
fi

if [[ "$second_duplicate" -lt 1 ]]; then
  echo "expected second run to detect duplicate dequeue"
  exit 1
fi

echo "scheduler queue test passed"
