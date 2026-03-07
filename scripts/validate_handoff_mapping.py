#!/usr/bin/env python3

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

from runtime_evidence_contract import load_json, validate_report


DEFAULT_TAXONOMY = Path("config/runtime-reason-taxonomy.json")
DEFAULT_SCHEMA = Path("contracts/runtime-handoff-evidence.schema.json")


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description="Validate Executor/Worker handoff field mapping")
    parser.add_argument("--required", default="contracts/handoff-required-fields.json")
    parser.add_argument("--map", default="contracts/executor-worker-handoff-map.json")
    parser.add_argument("--sample", default="fixtures/handoff-packet.sample.json")
    parser.add_argument("--output", default="runtime-artifacts/interface/handoff-smoke-report.json")
    parser.add_argument("--run-id", default=f"handoff-map-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    args = parser.parse_args()

    req = load_json(Path(args.required)).get("required_fields", [])
    fmap = load_json(Path(args.map)).get("field_map", {})
    sample = load_json(Path(args.sample))

    missing_in_map = [f for f in req if f not in fmap]
    missing_in_sample = [f for f in req if f not in sample]

    runtime_input = {}
    for src, dst in fmap.items():
        if src in sample:
            runtime_input[dst] = sample[src]

    missing_runtime_fields = [fmap[f] for f in req if f in fmap and fmap[f] not in runtime_input]

    mismatch_count = len(missing_in_map) + len(missing_in_sample) + len(missing_runtime_fields)
    verdict = "pass" if mismatch_count == 0 else "fail"
    reason_code = "ok" if mismatch_count == 0 else "handoff_mapping_mismatch"
    taxonomy = load_json(DEFAULT_TAXONOMY)

    report = {
        "generated_at_utc": now_utc(),
        "run_id": args.run_id,
        "verdict": verdict,
        "reason_code": reason_code,
        "reason_taxonomy_version": int(taxonomy.get("version", 0)),
        "mismatch_count": mismatch_count,
        "missing_in_map": missing_in_map,
        "missing_in_sample": missing_in_sample,
        "missing_runtime_fields": missing_runtime_fields,
        "runtime_input": runtime_input,
    }

    validate_report(report, DEFAULT_SCHEMA, DEFAULT_TAXONOMY)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")

    print(f"report written: {out}")
    print(f"verdict={verdict} reason_code={reason_code} mismatch_count={mismatch_count}")
    return 0 if verdict == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
