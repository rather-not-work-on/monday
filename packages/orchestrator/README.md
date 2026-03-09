# orchestrator

Coordinate coarse runtime flow across kernel and executor.

- consume kernel and executor through typed ports only
- compose provider, telemetry, and messaging adapters without redefining their payloads
- do not inspect executor internals beyond shared types
