import { SubtaskDelegator } from "@rather-not-work-on/agent-kernel";
import type { MissionInput, RunRef } from "@rather-not-work-on/contract-bindings";
import { RalphLoopExecutor } from "@rather-not-work-on/executor-ralph-loop";

export class MissionOrchestrator {
  private readonly delegator = new SubtaskDelegator();
  private readonly executor = new RalphLoopExecutor();

  createRun(mission: MissionInput): RunRef {
    const plan = this.delegator.plan(mission);
    this.executor.execute(mission);
    return {
      runId: `${mission.missionId}:${plan.tasks.length}`,
      status: "queued",
    };
  }
}
