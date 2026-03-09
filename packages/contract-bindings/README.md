# contract-bindings

Expose shared runtime contract types consumed by monday runtime packages.

- import shared execution vocabulary here
- define repo-local runtime ports and envelopes here before behavior code adopts them
- do not place runtime logic here
- provider, telemetry, and messaging adapters must depend on these interfaces instead of inventing their own public payloads
