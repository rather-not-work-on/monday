import type {
  ExecutorLoopDependencies,
  ExecutorResult,
  MissionInput,
  SubtaskHandoff,
} from "@rather-not-work-on/contract-bindings";

import { buildExecutorEvent } from "./event_policy.js";

export class RalphLoopExecutor {
  constructor(private readonly dependencies: ExecutorLoopDependencies) {}

  execute(context: MissionInput, handoff?: SubtaskHandoff): ExecutorResult {
    const runId = handoff ? handoff.handoffId : `${context.missionId}:root`;
    const providerOutcome = this.dependencies.provider.invoke({
      envelope: {
        runId,
        missionId: context.missionId,
        objective: context.objective,
        taskId: handoff?.taskId,
        handoffId: handoff?.handoffId,
      },
    });

    this.dependencies.telemetry?.emit(buildExecutorEvent(context, providerOutcome, handoff));

    this.dependencies.messaging?.acknowledge(runId);

    return providerOutcome;
  }

  cancel(runId: string, reason: string): { runId: string; canceled: boolean; reason: string } {
    return {
      runId,
      canceled: true,
      reason,
    };
  }
}
