# Runtime Integration Runbook

## Goal
Run a deterministic handoff-to-scheduler integration cycle and replay check for monday runtime.

## Contract Inputs
- runbook contract: `config/runtime-integration-runbook-contract.json`
- handoff sample: `fixtures/handoff-packet.sample.json`
- queue sample shape: `fixtures/queue.sample.json`
- evidence schemas:
  - `contracts/runtime-handoff-evidence.schema.json`
  - `contracts/runtime-scheduler-evidence.schema.json`
  - `contracts/runtime-integration-evidence.schema.json`

## Command (Single Integration Run)
```bash
RUN_ID="runtime-integration-$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="/tmp/monday-runtime-integration-$RUN_ID"
mkdir -p "$OUT_DIR"

python3 scripts/integrate_planningops_handoff.py \
  --run-id "$RUN_ID" \
  --handoff-report "$OUT_DIR/handoff-smoke-report.json" \
  --queue-out "$OUT_DIR/queue.from-planningops.json" \
  --scheduler-report "$OUT_DIR/scheduler-run-report.json" \
  --integration-report "$OUT_DIR/planningops-handoff-report.json" \
  --idempotency "$OUT_DIR/idempotency.json" \
  --transition-log "$OUT_DIR/scheduler.ndjson"

python3 scripts/validate_runtime_evidence.py \
  --kind scheduler \
  --report "$OUT_DIR/scheduler-run-report.json" \
  --output "$OUT_DIR/scheduler-validation-report.json"

python3 scripts/validate_runtime_evidence.py \
  --kind integration \
  --report "$OUT_DIR/planningops-handoff-report.json" \
  --output "$OUT_DIR/integration-validation-report.json"
```

## Replay Pass Check
Run scheduler again against the same queue and idempotency state.

```bash
python3 scripts/scheduler_queue.py \
  --queue "$OUT_DIR/queue.from-planningops.json" \
  --run-id "${RUN_ID}-replay" \
  --idempotency "$OUT_DIR/idempotency.json" \
  --report "$OUT_DIR/scheduler-replay-report.json" \
  --transition-log "$OUT_DIR/scheduler.ndjson"

python3 scripts/validate_runtime_evidence.py \
  --kind scheduler \
  --report "$OUT_DIR/scheduler-replay-report.json" \
  --output "$OUT_DIR/scheduler-replay-validation-report.json"
```

Expected replay signal:
- `scheduler-replay-report.json` has `verdict=pass`
- `reason_code=duplicates_detected`
- `duplicate_count >= 1`

## Generated Artifacts
- `$OUT_DIR/handoff-smoke-report.json`
- `$OUT_DIR/queue.from-planningops.json`
- `$OUT_DIR/scheduler-run-report.json`
- `$OUT_DIR/planningops-handoff-report.json`
- `$OUT_DIR/scheduler-replay-report.json`
- `$OUT_DIR/scheduler.ndjson`

## Healthy Signals
- integration report has `verdict=pass`
- integration `reason_code=ok`
- scheduler run has `dequeued_count >= 1`
- scheduler run has `blocked_count == 0`
- replay run reports duplicate detection without schema violations

## Rollback Trigger
Trigger rollback if one of:
1. integration report is not `verdict=pass`
2. integration `reason_code != ok`
3. scheduler replay does not report duplicate detection

Immediate action:
- stop runtime apply loop
- preserve `$OUT_DIR` evidence
- open follow-up issue with `runtime_integration_replay_regression`
