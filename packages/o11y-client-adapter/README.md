# o11y-client-adapter

Bridge monday runtime events to the external observability gateway boundary.

- implement the monday-owned telemetry emit port
- normalize runtime event envelopes before transport wiring
- do not own replay policy
- direct sink integration lands in follow-up cards
