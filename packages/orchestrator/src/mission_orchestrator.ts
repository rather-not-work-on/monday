import { buildHandoffPlan, SubtaskDelegator } from "@rather-not-work-on/agent-kernel";
import type { MissionInput, RunRef } from "@rather-not-work-on/contract-bindings";
import type { MissionOrchestratorDependencies } from "./orchestrator_ports.js";
import { buildDefaultExecutor } from "./default_runtime_dependencies.js";
import { buildRunRef } from "./run_lifecycle.js";

export class MissionOrchestrator {
  private readonly dependencies: MissionOrchestratorDependencies;

  constructor(dependencies?: Partial<MissionOrchestratorDependencies>) {
    this.dependencies = {
      planner: dependencies?.planner ?? new SubtaskDelegator(),
      executor: dependencies?.executor ?? buildDefaultExecutor(),
    };
  }

  createRun(mission: MissionInput): RunRef {
    const plan = this.dependencies.planner.plan(mission);
    const handoffs = buildHandoffPlan(mission, plan);
    const primaryHandoff = handoffs[0];
    const outcome = this.dependencies.executor.execute(mission, primaryHandoff);
    const runId = primaryHandoff?.handoffId ?? `${mission.missionId}:root`;

    return buildRunRef(runId, outcome);
  }
}
