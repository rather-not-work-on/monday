#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

mission_file="$tmp_dir/mission.json"
runtime_profile_file="$tmp_dir/runtime-profiles.json"
output_path="$tmp_dir/local-runtime-smoke.json"

cat >"$mission_file" <<'JSON'
{
  "missionId": "issue-bridge-smoke",
  "objective": "Verify mission-file input is preserved by monday local runtime smoke."
}
JSON

cat >"$runtime_profile_file" <<'JSON'
{
  "active_profile": "local",
  "profiles": {
    "local": {
      "execution_mode": "local",
      "litellm_base_url": "http://127.0.0.1:4000",
      "langfuse_host": "http://127.0.0.1:3001"
    }
  }
}
JSON

python3 "${ROOT_DIR}/scripts/run_local_runtime_smoke.py" \
  --mission-file "$mission_file" \
  --runtime-profile-file "$runtime_profile_file" \
  --profile "local" \
  --run-id "mission-file-contract" \
  --output "$output_path"

python3 - <<'PY' "$output_path"
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert report["mission_source"] == "mission_file", report
assert report["mission_file"], report
assert report["requested_mission"]["missionId"] == "issue-bridge-smoke", report
assert report["requested_mission"]["objective"] == "Verify mission-file input is preserved by monday local runtime smoke.", report
assert report["mission"]["missionId"] == "issue-bridge-smoke", report
assert report["mission"]["objective"] == report["requested_mission"]["objective"], report
assert report["verdict"] in {"pass", "skip"}, report
assert report["reason_code"] in {"ok", "tsx_fetch_unavailable_offline"}, report
PY

echo "local runtime smoke mission-file contract ok"
