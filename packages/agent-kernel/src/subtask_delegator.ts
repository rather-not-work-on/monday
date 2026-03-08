import type { MissionInput, RunRef, SubtaskHandoff, TaskPlan } from "@rather-not-work-on/contract-bindings";

export class SubtaskDelegator {
  plan(mission: MissionInput): TaskPlan {
    return { tasks: [mission.objective] };
  }

  delegate(handoff: SubtaskHandoff): RunRef {
    return {
      runId: handoff.handoffId,
      status: "queued",
    };
  }
}
