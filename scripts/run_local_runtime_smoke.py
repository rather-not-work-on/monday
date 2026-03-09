#!/usr/bin/env python3

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def build_ts_smoke_source(runtime_profile_file: Path, profile_name: str, mission_id: str, objective: str) -> str:
    profile_arg = json.dumps(profile_name)
    runtime_profile_arg = json.dumps(str(runtime_profile_file))
    mission_id_arg = json.dumps(mission_id)
    objective_arg = json.dumps(objective)
    return f"""
import {{ readFileSync }} from "node:fs";
import {{ buildHandoffPlan, SubtaskDelegator }} from "../../packages/agent-kernel/src/index.ts";
import {{ buildDefaultLocalExecutor, deriveRunLifecycle, resolveLocalRuntimeProfile }} from "../../packages/orchestrator/src/index.ts";

const runtimeProfileFile = {runtime_profile_arg};
const profileName = {profile_arg};
const mission = {{
  missionId: {mission_id_arg},
  objective: {objective_arg},
}};

const catalog = JSON.parse(readFileSync(runtimeProfileFile, "utf8"));
const profile = resolveLocalRuntimeProfile(catalog, profileName);
const planner = new SubtaskDelegator();
const taskPlan = planner.plan(mission);
const handoffs = buildHandoffPlan(mission, taskPlan);
const handoff = handoffs[0];
const executor = buildDefaultLocalExecutor({{ profile }});
const outcome = executor.execute(mission, handoff);
const lifecycle = deriveRunLifecycle(outcome);
const runId = handoff?.handoffId ?? `${{mission.missionId}}:root`;

console.log(
  JSON.stringify({{
    runtimeProfile: profile,
    mission,
    taskPlan,
    handoff,
    outcome,
    lifecycle,
    runId,
  }}),
);
"""


def run_ts_smoke(repo_root: Path, runtime_profile_file: Path, profile_name: str, mission_id: str, objective: str):
    def resolve_tsx_command(temp_path: Path) -> list[str]:
        local_name = "tsx.cmd" if os.name == "nt" else "tsx"
        local_tsx = repo_root / "node_modules" / ".bin" / local_name
        if local_tsx.exists():
            return [str(local_tsx), str(temp_path)]
        return ["npx", "--yes", "tsx", str(temp_path)]

    temp_dir = repo_root / "runtime-artifacts" / "tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".ts", dir=temp_dir, delete=False, encoding="utf-8") as handle:
        temp_path = Path(handle.name)
        handle.write(build_ts_smoke_source(runtime_profile_file, profile_name, mission_id, objective))

    command = resolve_tsx_command(temp_path)
    try:
        completed = subprocess.run(command, cwd=repo_root, capture_output=True, text=True)
    finally:
        temp_path.unlink(missing_ok=True)

    return completed, command


def is_offline_tsx_fetch_error(stderr: str) -> bool:
    normalized = stderr.lower()
    return "enotfound" in normalized and "registry.npmjs.org/tsx" in normalized


def main():
    parser = argparse.ArgumentParser(description="Run a monday local runtime smoke through the profiled executor path")
    parser.add_argument(
        "--runtime-profile-file",
        default="../platform-planningops/planningops/config/runtime-profiles.json",
        help="Path to the shared runtime profile catalog",
    )
    parser.add_argument("--profile", default="local", help="Runtime profile id to resolve")
    parser.add_argument("--mission-id", default="local-mission-smoke", help="Mission id used for the smoke run")
    parser.add_argument(
        "--objective",
        default="Verify local runtime composition through profiled provider and telemetry adapters.",
        help="Mission objective used for the smoke run",
    )
    parser.add_argument(
        "--run-id",
        default=f"local-runtime-smoke-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        help="Smoke run id used for evidence output",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional explicit output path. Defaults to runtime-artifacts/smoke/<run_id>.json",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    runtime_profile_file = (repo_root / args.runtime_profile_file).resolve()
    if not runtime_profile_file.exists():
        raise SystemExit(f"runtime profile file not found: {runtime_profile_file}")

    completed, ts_command = run_ts_smoke(repo_root, runtime_profile_file, args.profile, args.mission_id, args.objective)
    errors = []
    warnings = []
    payload = {}
    if completed.returncode == 0:
        try:
            payload = json.loads(completed.stdout.strip())
        except json.JSONDecodeError as exc:
            errors.append(f"ts_smoke_output_invalid_json: {exc}")
    else:
        if ts_command[:3] == ["npx", "--yes", "tsx"] and is_offline_tsx_fetch_error(completed.stderr):
            warnings.append("tsx_fetch_unavailable_offline")
        else:
            errors.append("ts_smoke_command_failed")

    lifecycle = payload.get("lifecycle") or {}
    if completed.returncode == 0 and lifecycle.get("status") == "terminal" and not errors:
        verdict = "pass"
        reason_code = "ok"
    elif warnings:
        verdict = "skip"
        reason_code = "tsx_fetch_unavailable_offline"
    else:
        verdict = "fail"
        reason_code = "local_runtime_smoke_failed"

    report = {
        "generated_at_utc": now_utc(),
        "run_id": args.run_id,
        "runtime_profile_file": str(runtime_profile_file),
        "runtime_profile": payload.get("runtimeProfile"),
        "mission": payload.get("mission"),
        "task_plan": payload.get("taskPlan"),
        "handoff": payload.get("handoff"),
        "executor_outcome": payload.get("outcome"),
        "lifecycle": lifecycle,
        "runtime_run_id": payload.get("runId"),
        "verdict": verdict,
        "reason_code": reason_code,
        "ts_command": [*ts_command[:-1], "<tempfile>"],
        "ts_exit_code": completed.returncode,
        "ts_stdout": completed.stdout.strip(),
        "ts_stderr": completed.stderr.strip(),
        "errors": errors,
        "warnings": warnings,
    }

    output_path = Path(args.output) if args.output else repo_root / "runtime-artifacts" / "smoke" / f"{args.run_id}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    print(f"report written: {output_path}")
    print(f"verdict={verdict} reason_code={reason_code} runtime_run_id={report.get('runtime_run_id')}")
    return 0 if verdict in {"pass", "skip"} else 1


if __name__ == "__main__":
    sys.exit(main())
