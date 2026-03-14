#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cd "$ROOT_DIR"

python3 scripts/export_worker_outcome_reflection_packet.py \
  --outcome-json fixtures/runtime-queue-worker-outcome.completed.sample.json \
  --output "$TMP_DIR/completed-packet.json" >/dev/null

python3 scripts/export_worker_outcome_reflection_packet.py \
  --outcome-json fixtures/runtime-queue-worker-outcome.retry-wait.sample.json \
  --output "$TMP_DIR/retry-packet.json" >/dev/null

python3 scripts/export_worker_outcome_reflection_packet.py \
  --outcome-json fixtures/runtime-queue-worker-outcome.dead-letter.sample.json \
  --output "$TMP_DIR/dead-letter-packet.json" >/dev/null

python3 - "$TMP_DIR/completed-packet.json" "$TMP_DIR/retry-packet.json" "$TMP_DIR/dead-letter-packet.json" <<'PY'
import json
import sys
from pathlib import Path

completed = json.loads(Path(sys.argv[1]).read_text())
retry = json.loads(Path(sys.argv[2]).read_text())
dead_letter = json.loads(Path(sys.argv[3]).read_text())

assert completed["packet_version"] == 1, completed
assert completed["source_repo"] == "rather-not-work-on/monday", completed
assert completed["source_contract_ref"] == "platform-contracts/schemas/runtime-queue-worker-outcome.schema.json", completed
assert completed["reflection_contract_ref"] == "planningops/contracts/worker-outcome-reflection-contract.md", completed
assert completed["reflection_hints"]["outcome_class"] == "completion", completed
assert completed["reflection_hints"]["completion_candidate"] is True, completed
assert completed["reflection_hints"]["allowed_decisions"] == ["continue", "goal_achieved"], completed
assert completed["reflection_hints"]["operator_attention_recommended"] is False, completed

assert retry["reflection_hints"]["outcome_class"] == "retry_wait", retry
assert retry["reflection_hints"]["completion_candidate"] is False, retry
assert retry["reflection_hints"]["retry_exhausted"] is False, retry
assert retry["reflection_hints"]["allowed_decisions"] == ["continue"], retry

assert dead_letter["reflection_hints"]["outcome_class"] == "dead_letter", dead_letter
assert dead_letter["reflection_hints"]["dead_letter"] is True, dead_letter
assert dead_letter["reflection_hints"]["retry_exhausted"] is True, dead_letter
assert dead_letter["reflection_hints"]["operator_attention_recommended"] is True, dead_letter
assert dead_letter["reflection_hints"]["allowed_decisions"] == ["replan_required", "operator_notify"], dead_letter
assert dead_letter["worker_outcome"]["dead_letter_reason"] == "retry_budget_exhausted", dead_letter

print("export worker outcome reflection packet test passed")
PY
