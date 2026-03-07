# monday

Runtime surface for UAP Executor/Worker integration.

## Scope (M2 baseline)
- Executor/Worker naming contract ADR
- Ralph Loop handoff packet to runtime input mapping
- Interface smoke validation for field mismatch detection
- repo-owned runtime evidence schemas for handoff, scheduler, and integration

## Key Files
- `docs/adr/adr-0001-executor-worker-naming.md`
- `docs/runbook/planningops-handoff-scheduler-runbook.md`
- `contracts/handoff-required-fields.json`
- `contracts/executor-worker-handoff-map.json`
- `contracts/runtime-*-evidence.schema.json`
- `config/runtime-reason-taxonomy.json`
- `scripts/validate_handoff_mapping.py`
- `scripts/validate_runtime_evidence.py`
- `scripts/integrate_planningops_handoff.py`

## Smoke Validation
```bash
python3 scripts/validate_handoff_mapping.py
python3 scripts/integrate_planningops_handoff.py --run-id handoff-integration-local
bash scripts/test_scheduler_queue.sh
python3 scripts/validate_contract_pin.py
bash scripts/test_contract_pin_validation.sh
```

## Local CI Baseline
- workflow: `.github/workflows/monday-local-ci.yml`
- checks:
  - handoff mapping smoke
  - planningops handoff integration smoke
  - scheduler evidence validation
  - contract pin validation
  - seeded failure guard (`test_contract_pin_validation.sh`)
- remediation guide: `docs/runbook/planningops-handoff-scheduler-runbook.md#contract-pin-remediation`
- evidence contracts:
  - `contracts/runtime-handoff-evidence.schema.json`
  - `contracts/runtime-scheduler-evidence.schema.json`
  - `contracts/runtime-integration-evidence.schema.json`
- default local evidence root: `runtime-artifacts/` (gitignored)
