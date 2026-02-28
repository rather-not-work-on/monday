#!/usr/bin/env python3

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description="Validate Executor/Worker handoff field mapping")
    parser.add_argument("--required", default="contracts/handoff-required-fields.json")
    parser.add_argument("--map", default="contracts/executor-worker-handoff-map.json")
    parser.add_argument("--sample", default="fixtures/handoff-packet.sample.json")
    parser.add_argument("--output", default="artifacts/interface/handoff-smoke-report.json")
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

    report = {
        "generated_at_utc": now_utc(),
        "verdict": verdict,
        "mismatch_count": mismatch_count,
        "missing_in_map": missing_in_map,
        "missing_in_sample": missing_in_sample,
        "missing_runtime_fields": missing_runtime_fields,
        "runtime_input": runtime_input,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")

    print(f"report written: {out}")
    print(f"verdict={verdict} mismatch_count={mismatch_count}")
    return 0 if verdict == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
