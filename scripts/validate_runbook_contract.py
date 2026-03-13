#!/usr/bin/env python3

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_contract(contract_path: Path) -> dict:
    contract = load_json(contract_path)
    runbook_path = Path(contract["runbook_path"])
    runbook_text = runbook_path.read_text(encoding="utf-8")

    missing_sections = []
    for section in contract.get("required_sections", []):
        if f"## {section}" not in runbook_text:
            missing_sections.append(section)

    missing_fragments = []
    for fragment in contract.get("required_fragments", []):
        if fragment not in runbook_text:
            missing_fragments.append(fragment)

    missing_artifacts = []
    for artifact in contract.get("required_artifacts", []):
        if artifact not in runbook_text:
            missing_artifacts.append(artifact)

    errors = []
    if missing_sections:
        errors.append(f"missing required sections: {', '.join(missing_sections)}")
    if missing_fragments:
        errors.append(f"missing required fragments: {', '.join(missing_fragments)}")
    if missing_artifacts:
        errors.append(f"missing required artifacts: {', '.join(missing_artifacts)}")

    return {
        "contract": contract,
        "runbook_path": str(runbook_path),
        "missing_sections": missing_sections,
        "missing_fragments": missing_fragments,
        "missing_artifacts": missing_artifacts,
        "errors": errors,
    }


def main(default_contract: str | None = None, description: str = "Validate monday runbook contract") -> int:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--contract", default=default_contract)
    parser.add_argument("--output", default="runtime-artifacts/validation/runbook-contract-validation.json")
    args = parser.parse_args()

    if not args.contract:
        raise SystemExit("--contract is required")

    contract_path = Path(args.contract)
    result = validate_contract(contract_path)
    errors = result["errors"]
    verdict = "pass" if not errors else "fail"

    payload = {
        "generated_at_utc": now_utc(),
        "contract_path": str(contract_path),
        "runbook_path": result["runbook_path"],
        "contract_version": int(result["contract"].get("version", 0)),
        "missing_sections": result["missing_sections"],
        "missing_fragments": result["missing_fragments"],
        "missing_artifacts": result["missing_artifacts"],
        "error_count": len(errors),
        "errors": errors,
        "verdict": verdict,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    print(f"report written: {out}")
    print(f"verdict={verdict} error_count={len(errors)}")
    return 0 if verdict == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
