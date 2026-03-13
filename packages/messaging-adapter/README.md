# messaging-adapter

Own user-channel relay and acknowledgement boundaries.

- implement the monday-owned acknowledgement port
- keep goal completion notification delivery and idempotency helpers in this package
- keep operator-channel transport adapters in this package so skills and CLIs stay thin wrappers
- do not create run state
- channel-specific integrations land in follow-up cards
