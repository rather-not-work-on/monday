# executor-ralph-loop

Own the loop execution boundary.

- depend on runtime ports from contract-bindings rather than concrete clients
- derive emitted telemetry events through a local executor event policy helper
- emit provider, telemetry, and acknowledgement calls through injected dependencies
