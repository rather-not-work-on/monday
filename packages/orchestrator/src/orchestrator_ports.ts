import type { ExecutorResult, MissionInput, SubtaskHandoff, TaskPlan } from "@rather-not-work-on/contract-bindings";

export interface MissionPlannerPort {
  plan(mission: MissionInput): TaskPlan;
}

export interface MissionExecutorPort {
  execute(context: MissionInput, handoff?: SubtaskHandoff): ExecutorResult;
}

export interface MissionOrchestratorDependencies {
  planner: MissionPlannerPort;
  executor: MissionExecutorPort;
}
