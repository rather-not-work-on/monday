# scripts

## Responsibility
Host repeatable runtime handoff, scheduler, and validation tooling.

## Contents
- handoff mapping validation
- runtime evidence validation
- planningops integration smoke
- scheduled queue cycle baseline entrypoint
- scheduler-native worker-outcome selector
- SQLite-backed queue store baseline entrypoint
- queue worker outcome transition CLI baseline
- local runtime smoke entrypoint
- operator channel delivery CLI baselines
- local outbox dispatch packet export baseline
- local outbox dispatch acknowledgement baseline
- local dispatch execution packet export baseline
- local dispatch cycle baseline
- supervisor handoff status update CLI
- supervisor handoff goal completion CLI
- generic runbook contract validation
- scheduler queue tests
- scheduled queue cycle tests
- scheduled worker-outcome selector tests
- queue store tests
- SQLite-backed scheduled queue cycle regression
- queue worker outcome transition tests
- queue worker outcome lifecycle regression
- local outbox dispatch packet tests
- local outbox dispatch acknowledgement tests
- local dispatch execution packet tests
- local dispatch cycle tests
- runtime integration runbook validation
- runtime integration guardrail regression

## Rules
- scripts should emit runtime output into `runtime-artifacts/` or `/tmp`, not Git-tracked paths
- repository topology drift must be caught by `test_module_readmes.sh`
