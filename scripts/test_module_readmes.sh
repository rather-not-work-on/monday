#!/usr/bin/env bash
set -euo pipefail

required_files=(
  "docs/repo-topology.md"
  "contracts/README.md"
  "config/README.md"
  "scripts/README.md"
  "docs/adr/README.md"
  "docs/runbook/README.md"
  "runtime-artifacts/README.md"
)

for path in "${required_files[@]}"; do
  if [[ ! -f "$path" ]]; then
    echo "missing required topology file: $path"
    exit 1
  fi
done

grep -q '`docs/repo-topology.md`' README.md
grep -q '`runtime-artifacts/README.md`' README.md
grep -q '| `contracts/` |' docs/repo-topology.md
grep -q '| `config/` |' docs/repo-topology.md
grep -q '| `scripts/` |' docs/repo-topology.md
grep -q '| `docs/adr/` |' docs/repo-topology.md
grep -q '| `docs/runbook/` |' docs/repo-topology.md
grep -q '| `runtime-artifacts/` |' docs/repo-topology.md

echo "monday module README topology contract ok"
