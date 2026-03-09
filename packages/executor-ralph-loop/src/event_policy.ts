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

function resolveReasonCode(result: ExecutorResult): string | undefined {
  if ("reasonCode" in result && typeof result.reasonCode === "string") {
    return result.reasonCode;
  }

  return undefined;
}

export function buildExecutorEvent(
  mission: MissionInput,
  result: ExecutorResult,
  handoff?: SubtaskHandoff
): TimelineEventEnvelope {
  return {
    runId: handoff ? handoff.handoffId : `${mission.missionId}:root`,
    missionId: mission.missionId,
    eventName: resolveEventName(result),
    detail: buildEventDetail(mission, handoff),
    taskId: handoff?.taskId,
    handoffId: handoff?.handoffId,
    source: "executor",
    resultType: result.resultType,
    reasonCode: resolveReasonCode(result),
  };
}
