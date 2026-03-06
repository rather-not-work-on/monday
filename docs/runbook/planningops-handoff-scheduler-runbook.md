# PlanningOps Handoff Scheduler Runbook

## Goal
Run one integration cycle from planningops handoff context into monday scheduler dequeue flow.

## Command
```bash
python3 scripts/integrate_planningops_handoff.py --run-id handoff-integration-<timestamp>
```

## Generated Artifacts
- `artifacts/integration/handoff-smoke-report.json`
- `artifacts/integration/queue.from-planningops.json`
- `artifacts/integration/scheduler-run-report.json`
- `artifacts/integration/planningops-handoff-report.json`
- `artifacts/integration/scheduler.ndjson`

## Healthy Signals
- handoff mapping `mismatch_count == 0`
- scheduler `dequeued_count >= 1`
- scheduler `blocked_count == 0`
- integration report `verdict == pass`

## Rollback Trigger
Trigger rollback if one of:
1. handoff mapping mismatch exists (`mismatch_count > 0`)
2. no card dequeued (`dequeued_count == 0`)
3. blocked cards exist (`blocked_count > 0`)

Immediate action:
- stop scheduler apply run
- keep queue in `Todo`/`Blocked`
- open follow-up issue with `handoff_mapping_mismatch|scheduler_no_dequeue|scheduler_blocked_cards`

## Contract Pin Remediation
Use this when `scripts/validate_contract_pin.py` fails in local CI.

1. Open `contracts/contract-pin.json`.
2. Confirm required fields:
   - `source_repo == rather-not-work-on/platform-contracts`
   - `consumer_repo == rather-not-work-on/monday`
   - `contract_bundle_version` format is `YYYY.MM.DD`
   - `pinned_contracts` includes:
     - `c1-run-lifecycle`
     - `c2-subtask-handoff`
     - `c3-executor-result`
     - `c8-plan-to-github-projection`
3. Re-run:

```bash
python3 scripts/validate_contract_pin.py
bash scripts/test_contract_pin_validation.sh
```
