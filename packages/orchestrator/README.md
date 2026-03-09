# orchestrator

Coordinate coarse runtime flow across kernel and executor.

- consume kernel and executor through typed ports only
- lift task plans into explicit handoff records before executor invocation
- derive run status through the local run lifecycle helper instead of inline conditionals
- compose provider, telemetry, and messaging adapters without redefining their payloads
- do not inspect executor internals beyond shared types
