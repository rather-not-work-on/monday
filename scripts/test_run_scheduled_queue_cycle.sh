#!/usr/bin/env bash
set -euo pipefail

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

python3 scripts/run_scheduled_queue_cycle.py \
  --queue fixtures/runtime-scheduler-queue.sample.json \
  --run-id test-scheduled-cycle-1 \
  --idempotency "$TMP_DIR/idempotency.json" \
  --report "$TMP_DIR/run-report-wave4-first.json" \
  --transition-log "$TMP_DIR/scheduled-cycle.ndjson"

python3 scripts/validate_runtime_evidence.py \
  --kind scheduler \
  --report "$TMP_DIR/run-report-wave4-first.json" \
  --output "$TMP_DIR/runtime-scheduler-wave4-first-validation.json"

first_reason_code=$(jq -r '.reason_code' "$TMP_DIR/run-report-wave4-first.json")
first_dequeued=$(jq -r '.dequeued_count' "$TMP_DIR/run-report-wave4-first.json")
first_blocked=$(jq -r '.blocked_count' "$TMP_DIR/run-report-wave4-first.json")

if [[ "$first_reason_code" != "blocked_dependencies" ]]; then
  echo "expected first run reason_code=blocked_dependencies, got $first_reason_code"
  exit 1
fi

if [[ "$first_dequeued" -lt 1 ]]; then
  echo "expected first run to dequeue at least one queue item"
  exit 1
fi

if [[ "$first_blocked" -lt 1 ]]; then
  echo "expected first run to report at least one blocked queue item"
  exit 1
fi

cat > "$TMP_DIR/queue-unblocked.json" <<'JSON'
{
  "queue_items": [
    {
      "queue_item_id": "queue-wave4-001",
      "goal_key": "uap-goal-driven-autonomy-wave4",
      "schedule_key": "local-tick-5m",
      "state": "ready",
      "idempotency_key": "wave4:queue-wave4-001",
      "priority_class": "standard",
      "retry_budget": {"max_attempts": 3},
      "retry_budget_remaining": 2,
      "attempt_count": 1,
      "dependency_keys": [],
      "escalation_policy_ref": "planningops/contracts/escalation-gate-contract.md",
      "completion_policy_ref": "planningops/contracts/goal-completion-contract.md"
    }
  ],
  "completed_queue_item_ids": []
}
JSON

python3 scripts/run_scheduled_queue_cycle.py \
  --queue "$TMP_DIR/queue-unblocked.json" \
  --run-id test-scheduled-cycle-2 \
  --idempotency "$TMP_DIR/idempotency.json" \
  --report "$TMP_DIR/run-report-wave4-second.json" \
  --transition-log "$TMP_DIR/scheduled-cycle.ndjson"

python3 scripts/validate_runtime_evidence.py \
  --kind scheduler \
  --report "$TMP_DIR/run-report-wave4-second.json" \
  --output "$TMP_DIR/runtime-scheduler-wave4-second-validation.json"

second_reason_code=$(jq -r '.reason_code' "$TMP_DIR/run-report-wave4-second.json")
second_duplicate=$(jq -r '.duplicate_count' "$TMP_DIR/run-report-wave4-second.json")

if [[ "$second_reason_code" != "duplicates_detected" ]]; then
  echo "expected second run reason_code=duplicates_detected, got $second_reason_code"
  exit 1
fi

if [[ "$second_duplicate" -lt 1 ]]; then
  echo "expected second run to detect duplicate dequeue"
  exit 1
fi

echo "scheduled queue cycle test passed"
