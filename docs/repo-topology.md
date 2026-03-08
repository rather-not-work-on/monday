# monday Topology

## Purpose
Fix the long-term repository boundaries for the Executor/Worker runtime before deeper implementation begins.

## Module Map
| Path | Responsibility | Allowed contents | Must not contain |
| --- | --- | --- | --- |
| `contracts/` | runtime-owned handoff, scheduler, and evidence contract surfaces | schemas, handoff maps, contract metadata | executable runtime logic |
| `config/` | static runtime taxonomies and defaults | declarative configuration | execution code |
| `scripts/` | repeatable handoff, scheduler, validation, and smoke tooling | local tooling and tests | hidden architectural decisions without documentation |
| `docs/adr/` | durable architecture decisions for runtime semantics | ADR markdown | runbooks or generated evidence |
| `docs/runbook/` | operator-facing runtime usage and remediation guidance | runbooks and procedures | contracts or executable code |
| `runtime-artifacts/` | gitignored local runtime evidence root | local smoke/integration outputs plus tracked README | committed runtime reports |

## Extension Rules
1. Add runtime contract/interface changes in `contracts/`.
2. Add static runtime configuration in `config/`.
3. Put repeatable handoff/scheduler/validation tooling in `scripts/`.
4. Record architectural decisions in `docs/adr/`.
5. Keep operator procedures in `docs/runbook/`.
6. Keep runtime evidence external to Git under `runtime-artifacts/`.

## Ownership Boundary
- `monday` owns the runtime surface implementing Executor/Worker behavior.
- Shared contract shape comes from `platform-contracts`.
- Planning/orchestration policy belongs upstream in `platform-planningops`.
