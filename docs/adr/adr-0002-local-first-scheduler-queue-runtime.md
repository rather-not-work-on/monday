# ADR-0002: Local-First Scheduler Queue Runtime

- Status: Accepted
- Date: 2026-03-14
- Owner: @JJBINY
- Related issue: platform-planningops#324

## Decision
- `monday` owns the scheduler and queue runtime.
- The first durable queue backend is local-first SQLite.
- The first scheduler entrypoint is a repo-owned CLI: `scripts/run_scheduled_queue_cycle.py`.
- `planningops` remains policy and evidence control plane only.

## Boundary Rule
- `planningops` may define:
  - goal briefs
  - active-goal registry
  - execution contracts
  - queue admission and retry policy
  - reflection and completion policy
- `monday` must own:
  - queue persistence
  - lease and heartbeat handling
  - dequeue and dispatch
  - retry wait and dead-letter execution
  - operator-channel delivery adapters

`planningops` must not host the scheduler daemon or queue backend.

## Runtime Topology

### Entry Surface
- `scripts/run_scheduled_queue_cycle.py`
  - local-first scheduler cycle entrypoint
  - reads queue policy and queue items
  - advances queue state
  - emits deterministic evidence

### Baseline Runtime Store
- initial persistence stays in repo-local SQLite under monday-owned runtime paths
- baseline helper modules may live in `scripts/` while the runtime is still CLI-first
- storage shape must remain replayable and migration-friendly

### Existing Package Responsibilities
- `packages/orchestrator`
  - lift queue-ready work into runtime handoff inputs
  - must not own persistence or lease storage
- `packages/agent-kernel`
  - keep mission decomposition and deterministic handoff construction
  - must not inspect queue storage directly
- `packages/executor-ralph-loop`
  - remain the execution boundary for loop work
  - must consume leased work through typed inputs, not direct queue mutation
- `packages/messaging-adapter`
  - remain the delivery surface for operator status and terminal completion

### Deferred Package Growth
Future extraction is allowed only if the baseline CLI becomes too large.
Candidate extractions:
- queue store helper
- lease manager helper
- scheduler cycle composition helper

These are refactors, not prerequisites for the first durable runtime.

## State Model
The canonical scheduler state vocabulary is:
- `scheduled`
- `ready`
- `leased`
- `running`
- `blocked`
- `retry_wait`
- `dead_letter`
- `completed`

Monday owns runtime transitions between those states.

## Storage Rule
- default backend: SQLite
- default operation mode: local-first single-node execution
- state and logs must be easy to inspect on disk during debugging
- migration to external storage must preserve the same queue semantics and evidence shape

## Consequences
- Codex recurring automation can be replaced later without moving control-plane truth out of planningops
- scheduler growth can remain simple at first because queue persistence and execution stay local
- monday can add real scheduling without re-embedding Slack/email logic into planningops
