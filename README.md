# monday

Runtime surface for UAP Executor/Worker integration.

## Scope (M2 baseline)
- Executor/Worker naming contract ADR
- Ralph Loop handoff packet to runtime input mapping
- Interface smoke validation for field mismatch detection

## Key Files
- `docs/adr/adr-0001-executor-worker-naming.md`
- `docs/runbook/planningops-handoff-scheduler-runbook.md`
- `contracts/handoff-required-fields.json`
- `contracts/executor-worker-handoff-map.json`
- `scripts/validate_handoff_mapping.py`
- `scripts/integrate_planningops_handoff.py`

## Smoke Validation
```bash
python3 scripts/validate_handoff_mapping.py
python3 scripts/integrate_planningops_handoff.py --run-id handoff-integration-local
python3 scripts/validate_contract_pin.py
bash scripts/test_contract_pin_validation.sh
```

## Local CI Baseline
- workflow: `.github/workflows/monday-local-ci.yml`
- checks:
  - handoff mapping smoke
  - planningops handoff integration smoke
  - contract pin validation
  - seeded failure guard (`test_contract_pin_validation.sh`)
- remediation guide: `docs/runbook/planningops-handoff-scheduler-runbook.md#contract-pin-remediation`
