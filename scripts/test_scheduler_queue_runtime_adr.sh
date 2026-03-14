#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path

adr = Path("docs/adr/adr-0002-local-first-scheduler-queue-runtime.md")
text = adr.read_text(encoding="utf-8")

required_fragments = [
    "# ADR-0002: Local-First Scheduler Queue Runtime",
    "- Status: Accepted",
    "scripts/run_scheduled_queue_cycle.py",
    "`planningops` remains policy and evidence control plane only",
    "default backend: SQLite",
    "packages/orchestrator",
    "packages/executor-ralph-loop",
    "`dead_letter`",
]
for fragment in required_fragments:
    assert fragment in text, fragment

print("scheduler queue runtime adr ok")
PY
