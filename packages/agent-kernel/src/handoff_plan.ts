import type { MissionInput, SubtaskHandoff, TaskPlan } from "@rather-not-work-on/contract-bindings";

function buildTaskId(missionId: string, taskIndex: number): string {
  return `${missionId}:task:${taskIndex + 1}`;
}

function buildHandoffId(missionId: string, taskId: string): string {
  return `${missionId}:handoff:${taskId}`;
}

export function buildHandoffPlan(mission: MissionInput, plan: TaskPlan): SubtaskHandoff[] {
  return plan.tasks.map((_task, taskIndex) => {
    const taskId = buildTaskId(mission.missionId, taskIndex);

    return {
      handoffId: buildHandoffId(mission.missionId, taskId),
      taskId,
    };
  });
}
