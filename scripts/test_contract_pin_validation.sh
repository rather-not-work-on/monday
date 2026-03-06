#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

INVALID_PIN="$TMP_DIR/contract-pin.invalid.json"
INVALID_REPORT="$TMP_DIR/contract-pin-invalid-report.json"
VALID_REPORT="$TMP_DIR/contract-pin-valid-report.json"

cat > "$INVALID_PIN" <<'JSON'
{
  "source_repo": "rather-not-work-on/platform-contracts",
  "contract_bundle_version": "2026.02.28",
  "pinned_contracts": [
    "c1-run-lifecycle",
    "c2-subtask-handoff",
    "c3-executor-result"
  ],
  "consumer_repo": "rather-not-work-on/monday"
}
JSON

if python3 "$ROOT_DIR/scripts/validate_contract_pin.py" --pin "$INVALID_PIN" --output "$INVALID_REPORT"; then
  echo "[FAIL] invalid pin unexpectedly passed"
  exit 1
fi

python3 "$ROOT_DIR/scripts/validate_contract_pin.py" --pin "$ROOT_DIR/contracts/contract-pin.json" --output "$VALID_REPORT"

echo "contract pin validation regression passed"
