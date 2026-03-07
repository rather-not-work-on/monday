#!/usr/bin/env python3

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

from runtime_evidence_contract import load_json, validate_report


DEFAULT_SCHEMA_BY_KIND = {
    "handoff": Path("contracts/runtime-handoff-evidence.schema.json"),
    "scheduler": Path("contracts/runtime-scheduler-evidence.schema.json"),
    "integration": Path("contracts/runtime-integration-evidence.schema.json"),
}
DEFAULT_TAXONOMY = Path("config/runtime-reason-taxonomy.json")


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description="Validate monday runtime evidence")
    parser.add_argument("--kind", choices=sorted(DEFAULT_SCHEMA_BY_KIND), required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--schema", default=None)
    parser.add_argument("--taxonomy", default=str(DEFAULT_TAXONOMY))
    parser.add_argument("--output", default="runtime-artifacts/validation/runtime-evidence-report.json")
    args = parser.parse_args()

    schema_path = Path(args.schema) if args.schema else DEFAULT_SCHEMA_BY_KIND[args.kind]
    report_doc = load_json(Path(args.report))
    errors = []
    try:
        validate_report(report_doc, schema_path, Path(args.taxonomy))
    except Exception as exc:  # noqa: BLE001
        errors.append(str(exc))

    verdict = "pass" if not errors else "fail"
    payload = {
        "generated_at_utc": now_utc(),
        "kind": args.kind,
        "report_path": args.report,
        "schema_path": str(schema_path),
        "taxonomy_path": args.taxonomy,
        "error_count": len(errors),
        "errors": errors,
        "verdict": verdict,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    print(f"report written: {out}")
    print(f"kind={args.kind} verdict={verdict} error_count={len(errors)}")
    return 0 if verdict == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
