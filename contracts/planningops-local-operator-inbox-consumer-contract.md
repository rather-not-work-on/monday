# PlanningOps Local Operator Inbox Consumer Contract

## Purpose
Define the monday-native consumer boundary for the promoted PlanningOps local operator inbox payload bridge.

This contract exists so:
- `monday` can accept one machine-readable inbox payload without reparsing `body_markdown`
- runtime launch planning stays deterministic and reproducible from promoted PlanningOps artifacts
- the next packet can wire execution against a stable monday-owned launch-request surface

## Canonical Boundary

PlanningOps owns:
- the promoted inbox payload bridge contract
- deterministic latest + stamped validation artifacts under `planningops/artifacts/validation/`
- the upstream day packet, mission packet, handoff report, and local operator report references

Monday owns:
- inbox bridge consumption
- launch-request materialization
- optional apply-time execution through `scripts/run_local_runtime_smoke.py`
- monday-side reports written under `runtime-artifacts/`

Monday must not:
- re-infer launch semantics from `payload.body_markdown`
- silently ignore `payload.status`, `needs_human_attention`, or local validation action lines
- mutate PlanningOps validation artifacts in place

## Canonical Inputs

Required input artifact:
- `../platform-planningops/planningops/artifacts/validation/monday-local-operator-inbox-payload.json`

Required upstream source artifacts referenced by the input payload:
- promoted day packet
- promoted mission packet
- promoted handoff report
- promoted local operator report

## Canonical Outputs

For every consumer run, monday must emit:
- launch request: `runtime-artifacts/integration/planningops-local-operator-inbox/<run-id>/launch-request.json`
- mission file: `runtime-artifacts/integration/planningops-local-operator-inbox/<run-id>/mission.json`
- consumer report: `runtime-artifacts/integration/planningops-local-operator-inbox/<run-id>/consumer-report.json`

When `mode=apply`, monday may also emit:
- runtime report: `runtime-artifacts/integration/planningops-local-operator-inbox/<run-id>/local-runtime-smoke.json`

## Consumer Report Shape

Top-level required fields:
1. `generated_at_utc`
2. `run_id`
3. `consumer_contract_ref`
4. `source_bridge_path`
5. `bridge_id`
6. `mode`
7. `verdict`
8. `reason_code`
9. `consumer_status`
10. `artifact_paths.launch_request_path`
11. `artifact_paths.mission_file_path`
12. `artifact_paths.report_path`
13. `artifact_paths.runtime_report_path`
14. `launch_request`

`launch_request` required fields:
1. `source_bridge_id`
2. `source_day_packet_id`
3. `source_mission_packet_id`
4. `mission_objective`
5. `planner_profile`
6. `launch_mode`
7. `local_model_route`
8. `first_action_command`
9. `monday_runtime_entrypoint_command`
10. `rollback_command`
11. `recommended_wait_minutes`
12. `needs_human_attention`
13. `local_validation_snapshot_status`
14. `local_validation_summary_lines`
15. `local_validation_action_lines`
16. `can_launch`
17. `block_reasons`
18. `runtime_command_args`
19. `source_artifacts.day_packet_path`
20. `source_artifacts.mission_packet_path`
21. `source_artifacts.handoff_report_path`
22. `source_artifacts.local_operator_report_path`

Optional fields:
- `runtime_input_overrides`
- `runtime_report_summary`
- `execution`

## Deterministic Rules

1. The consumer must reuse structured payload fields and source artifact refs instead of reparsing markdown.
2. `launch_request.can_launch` is fail-closed:
   - false when `payload.status != ready`
   - false when `payload.needs_human_attention == true`
   - false when `payload.local_validation_action_lines` is non-empty
   - otherwise true
3. The generated mission file must preserve the promoted mission objective and mission packet id.
4. The runtime command must be materialized as direct argv for `scripts/run_local_runtime_smoke.py`, not by shell parsing `monday_runtime_entrypoint_command`.
5. When explicit runtime config override files are provided, the consumer must validate they exist and pass them through as `--planner-runtime-config` / `--runtime-profile-file`.
6. `mode=apply` must refuse to execute when `can_launch` is false.

## Cross-Artifact Consistency Rules

- payload `planner_profile`, `launch_mode`, `local_model_route`, `rollback_command`, and `monday_runtime_entrypoint_command` must match the promoted mission packet
- payload `day_packet_id` and `mission_packet_id` must match the promoted day packet when present
- every source artifact path referenced by the payload must exist

## Failure Rules

- missing input bridge payload is fail-fast
- missing source artifacts referenced by the bridge payload are fail-fast
- missing `mission_objective`, `planner_profile`, `first_action_command`, `rollback_command`, or `monday_runtime_entrypoint_command` is fail-fast
- apply-mode execution while `can_launch=false` is fail-closed with `verdict=blocked`

## Validation

- `scripts/consume_planningops_local_operator_inbox_payload.py`
- `scripts/test_consume_planningops_local_operator_inbox_payload.sh`
