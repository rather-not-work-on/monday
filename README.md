# monday

Runtime surface for UAP Executor/Worker integration.

## Scope (M2 baseline)
- Executor/Worker naming contract ADR
- Ralph Loop handoff packet to runtime input mapping
- Interface smoke validation for field mismatch detection
- repo-owned runtime evidence schemas for handoff, scheduler, and integration
- queue worker outcome transition baseline for durable local runtime state changes

## Key Files
- `docs/adr/adr-0001-executor-worker-naming.md`
- `docs/adr/adr-0002-local-first-scheduler-queue-runtime.md`
- `docs/runbook/planningops-handoff-scheduler-runbook.md`
- `docs/runbook/runtime-integration-runbook.md`
- `docs/runbook/goal-completion-notifier.md`
- `docs/runbook/operator-channel-adapter.md`
- `docs/runbook/planningops-supervisor-handoff.md`
- `contracts/handoff-required-fields.json`
- `contracts/executor-worker-handoff-map.json`
- `contracts/runtime-*-evidence.schema.json`
- `config/runtime-reason-taxonomy.json`
- `config/local-operator-channel-profiles.json`
- `config/runtime-integration-runbook-contract.json`
- `config/goal-completion-notifier-runbook-contract.json`
- `config/operator-channel-adapter-runbook-contract.json`
- `config/planningops-supervisor-handoff-runbook-contract.json`
- `scripts/validate_handoff_mapping.py`
- `scripts/validate_runtime_evidence.py`
- `scripts/integrate_planningops_handoff.py`
- `scripts/runtime_queue_store.py`
- `scripts/record_queue_worker_outcome.py`
- `scripts/test_record_queue_worker_outcome_cli.sh`
- `scripts/test_record_queue_worker_outcome.sh`
- `scripts/validate_runbook_contract.py`
- `scripts/validate_runtime_integration_runbook.py`
- `scripts/run_scheduled_queue_cycle.py`
- `scripts/test_runtime_guardrails.sh`
- `scripts/operator_channel_local_outbox.py`
- `scripts/test_run_scheduled_queue_cycle.sh`
- `scripts/send_supervisor_status_update.py`
- `scripts/send_supervisor_goal_completion.py`

Topology guide:
- `docs/repo-topology.md`
- `contracts/README.md`
- `config/README.md`
- `scripts/README.md`
- `docs/adr/README.md`
- `docs/runbook/README.md`
- `runtime-artifacts/README.md`

## Workspace Bootstrap
- `package.json`
- `pnpm-workspace.yaml`
- `tsconfig.base.json`

The workspace bootstrap is intentionally thin in this step.

- runtime package directories land in follow-up cards
- current Python scripts remain the validation and smoke harness
- local runtime outputs stay under `runtime-artifacts/`
- supervisor handoff delivery entrypoints stay in `scripts/` until transport packages are introduced

Current scaffolded runtime packages:
- `packages/contract-bindings`
- `packages/agent-kernel`
- `packages/executor-ralph-loop`
- `packages/orchestrator`
- `packages/provider-client-adapter`
- `packages/o11y-client-adapter`
- `packages/messaging-adapter`

## Smoke Validation
```bash
python3 scripts/validate_handoff_mapping.py
python3 scripts/integrate_planningops_handoff.py --run-id handoff-integration-local
bash scripts/test_run_scheduled_queue_cycle.sh
bash scripts/test_run_scheduled_queue_cycle_store.sh
bash scripts/test_runtime_queue_store.sh
bash scripts/test_record_queue_worker_outcome_cli.sh
bash scripts/test_record_queue_worker_outcome.sh
bash scripts/test_operator_channel_delivery_cli.sh
bash scripts/test_send_reflection_decision_update.sh
bash scripts/test_supervisor_status_update_cli.sh
bash scripts/test_supervisor_goal_completion_cli.sh
bash scripts/test_scheduler_queue.sh
bash scripts/test_runtime_guardrails.sh
python3 scripts/validate_contract_pin.py
bash scripts/test_contract_pin_validation.sh
```

## Local CI Baseline
- workflow: `.github/workflows/monday-local-ci.yml`
- checks:
  - handoff mapping smoke
  - planningops handoff integration smoke
  - scheduler evidence validation
  - SQLite queue store regression (`scripts/test_runtime_queue_store.sh`)
  - SQLite-backed scheduled queue cycle regression (`scripts/test_run_scheduled_queue_cycle_store.sh`)
  - worker outcome lifecycle regression (`scripts/test_record_queue_worker_outcome.sh`)
  - contract pin validation
  - seeded failure guard (`test_contract_pin_validation.sh`)
  - topology/module README regression (`scripts/test_module_readmes.sh`)
- remediation guide: `docs/runbook/planningops-handoff-scheduler-runbook.md#contract-pin-remediation`
- runtime integration replay guide: `docs/runbook/runtime-integration-runbook.md`
- evidence contracts:
  - `contracts/runtime-handoff-evidence.schema.json`
  - `contracts/runtime-scheduler-evidence.schema.json`
  - `contracts/runtime-integration-evidence.schema.json`
- default local evidence root: `runtime-artifacts/` (gitignored)

## PR Hygiene
- template: `.github/pull_request_template.md`
- review gate: `.github/workflows/pr-review-gate.yml`
- external repo PRs must include a repo-qualified planningops issue ref
- example: `Closes rather-not-work-on/platform-planningops#207`

Generated local runtime outputs stay under `runtime-artifacts/` and remain gitignored except for the tracked module README.
