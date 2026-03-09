import type {
  ExecutorResult,
  MissionInput,
  SubtaskHandoff,
  TimelineEventEnvelope,
} from "@rather-not-work-on/contract-bindings";

function resolveEventName(result: ExecutorResult): TimelineEventEnvelope["eventName"] {
  switch (result.resultType) {
    case "complete":
      return "executor.completed";
    case "partial":
      return "executor.partial";
    case "canceled":
      return "executor.canceled";
    case "failed":
      return "executor.failed";
  }
}

function buildEventDetail(mission: MissionInput, handoff?: SubtaskHandoff): string {
  if (!handoff) {
    return `mission:${mission.missionId}:root`;
  }

  return `mission:${mission.missionId}:task:${handoff.taskId}`;
}

export function buildExecutorEvent(
  mission: MissionInput,
  result: ExecutorResult,
  handoff?: SubtaskHandoff
): TimelineEventEnvelope {
  return {
    runId: handoff ? handoff.handoffId : `${mission.missionId}:root`,
    eventName: resolveEventName(result),
    detail: buildEventDetail(mission, handoff),
  };
}
