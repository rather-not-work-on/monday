import type { ExecutorResult, MissionInput, TaskPlan } from "@rather-not-work-on/contract-bindings";

export interface MissionPlannerPort {
  plan(mission: MissionInput): TaskPlan;
}

export interface MissionExecutorPort {
  execute(context: MissionInput): ExecutorResult;
}

export interface MissionOrchestratorDependencies {
  planner: MissionPlannerPort;
  executor: MissionExecutorPort;
}
