# ADR-0001: Executor/Worker Naming Contract

- Status: Accepted
- Date: 2026-02-28
- Owner: @JJBINY
- Related issue: platform-planningops#20

## Decision
- External contract term is fixed to `Executor`.
- Internal implementation unit term is fixed to `Worker`.

## Boundary Rule
- APIs, docs, and inter-repo contracts expose `Executor`.
- Internal runtime module and execution loop implementation use `Worker`.

## Consequence
- naming drift is prevented across planningops/provider/o11y/runtime surfaces
- implementation refactor can happen without changing external contract language
