# scripts

## Responsibility
Host repeatable runtime handoff, scheduler, and validation tooling.

## Contents
- handoff mapping validation
- runtime evidence validation
- planningops integration smoke
- scheduled queue cycle baseline entrypoint
- SQLite-backed queue store baseline entrypoint
- local runtime smoke entrypoint
- operator channel delivery CLI baselines
- supervisor handoff status update CLI
- supervisor handoff goal completion CLI
- generic runbook contract validation
- scheduler queue tests
- scheduled queue cycle tests
- queue store tests
- runtime integration runbook validation
- runtime integration guardrail regression

## Rules
- scripts should emit runtime output into `runtime-artifacts/` or `/tmp`, not Git-tracked paths
- repository topology drift must be caught by `test_module_readmes.sh`
