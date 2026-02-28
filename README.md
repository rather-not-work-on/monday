# monday

Runtime surface for UAP Executor/Worker integration.

## Scope (M2 baseline)
- Executor/Worker naming contract ADR
- Ralph Loop handoff packet to runtime input mapping
- Interface smoke validation for field mismatch detection

## Key Files
- `docs/adr/adr-0001-executor-worker-naming.md`
- `contracts/handoff-required-fields.json`
- `contracts/executor-worker-handoff-map.json`
- `scripts/validate_handoff_mapping.py`

## Smoke Validation
```bash
python3 scripts/validate_handoff_mapping.py
```
