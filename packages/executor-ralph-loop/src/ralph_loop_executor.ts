import type { ExecutorResult, MissionInput, RunRef, SubtaskHandoff } from "@rather-not-work-on/contract-bindings";

export class RalphLoopExecutor {
  execute(context: MissionInput, handoff?: SubtaskHandoff): ExecutorResult {
    return {
      resultType: handoff ? "partial" : "complete",
    };
  }

  cancel(run: RunRef, reason: string): { runId: string; canceled: boolean; reason: string } {
    return {
      runId: run.runId,
      canceled: true,
      reason,
    };
  }
}
