# ADR-0002: Local-First Scheduler Queue Runtime

## Status
Accepted

## Date
2026-03-14

## Context
Goal-driven autonomy wave4 moves scheduler runtime ownership to `monday` while `platform-planningops` remains the control tower for goal, admission, retry, escalation, and completion policy.

The runtime entrypoint must support the shared queue-item policy contract from `platform-contracts` and remain compatible with existing scheduler evidence validation already used by local guardrails.

## Decision
`monday` adopts a local-first scheduler queue runtime topology:

1. Queue cycle entrypoint: `scripts/run_scheduled_queue_cycle.py`.
2. Shared queue policy shape: `platform-contracts/schemas/runtime-scheduler-queue-item.schema.json`.
3. Idempotency store: local JSON state under `runtime-artifacts/scheduler-cycle/`.
4. Transition log: append-only NDJSON under `runtime-artifacts/transition-log/`.
5. Scheduler report contract: `contracts/runtime-scheduler-evidence.schema.json`.

The queue cycle accepts both:
- Wave4 queue-item docs (`queue_items` + `completed_queue_item_ids`) validated against shared schema.
- Legacy queue docs (`items` + `completed_issues`) to keep current integration smoke stable while migration is in progress.

## Ownership Boundary
- `platform-planningops`: policy generation, active-goal truth, and completion decisions.
- `platform-contracts`: shared queue item schema.
- `monday`: queue runtime execution, idempotent dequeue, dependency gating, transition evidence.

`monday` must not redefine shared policy fields such as `goal_key`, `schedule_key`, `idempotency_key`, `dependency_keys`, `retry_budget`, `escalation_policy_ref`, and `completion_policy_ref`.

## Consequences
Positive:
- Wave4 gets a monday-owned scheduler cycle entrypoint that can replace Codex-hosted recurring execution later.
- Queue runtime semantics are shared-contract driven instead of prompt-local.
- Existing guardrail tests continue to run through backward compatibility.

Tradeoffs:
- The baseline keeps JSON-file idempotency and transition logs rather than durable SQLite storage in this wave.
- Scheduler evidence currently remains issue-number oriented; queue-native evidence can be promoted in a follow-up contract wave.

## Follow-ups
- Promote queue-native scheduler evidence schema once downstream consumers migrate from `issue_number` assumptions.
- Add SQLite-backed queue persistence and lease lifecycle once wave4 baseline is merged and stable.
