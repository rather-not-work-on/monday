import type {
  MissionInput,
  ProviderInvocationOutcome,
  ProviderInvocationPort,
  ProviderInvocationRequest,
  SubtaskHandoff,
  TaskExecutionEnvelope,
} from "@rather-not-work-on/contract-bindings";

export interface ProviderRequestInput {
  mission: MissionInput;
  handoff?: SubtaskHandoff;
  preferredProviderKey?: string;
  fallbackProviderKeys?: string[];
}

function buildExecutionEnvelope(mission: MissionInput, handoff?: SubtaskHandoff): TaskExecutionEnvelope {
  return {
    runId: handoff ? handoff.handoffId : `${mission.missionId}:root`,
    missionId: mission.missionId,
    objective: mission.objective,
    taskId: handoff?.taskId,
    handoffId: handoff?.handoffId,
  };
}

function buildInvocationPrompt(mission: MissionInput, handoff?: SubtaskHandoff): string {
  if (!handoff) {
    return mission.objective.trim();
  }

  return `${mission.objective.trim()}\n\nTask focus: ${handoff.taskId}`.trim();
}

export function buildProviderRequest(input: ProviderRequestInput): ProviderInvocationRequest {
  return {
    envelope: buildExecutionEnvelope(input.mission, input.handoff),
    prompt: buildInvocationPrompt(input.mission, input.handoff),
    preferredProviderKey: input.preferredProviderKey,
    fallbackProviderKeys: input.fallbackProviderKeys,
  };
}

export class ProviderClient implements ProviderInvocationPort {
  invoke(request: ProviderInvocationRequest): ProviderInvocationOutcome {
    const providerKey = request.preferredProviderKey ?? request.fallbackProviderKeys?.[0];

    return {
      resultType: "complete",
      reasonCode: "provider_client_stubbed",
      providerKey,
      outputText: request.prompt,
    };
  }
}
