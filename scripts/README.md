# scripts

## Responsibility
Host repeatable runtime handoff, scheduler, and validation tooling.

## Contents
- handoff mapping validation
- runtime evidence validation
- planningops integration smoke
- scheduler queue tests

## Rules
- scripts should emit runtime output into `runtime-artifacts/` or `/tmp`, not Git-tracked paths
- repository topology drift must be caught by `test_module_readmes.sh`
