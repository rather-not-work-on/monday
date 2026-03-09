export interface TaskExecutionEnvelope {
  runId: string;
  missionId: string;
  objective: string;
  taskId?: string;
  handoffId?: string;
}

export interface ProviderInvocationRequest {
  envelope: TaskExecutionEnvelope;
  prompt: string;
  preferredProviderKey?: string;
  fallbackProviderKeys?: string[];
}

export interface ProviderInvocationOutcome {
  resultType: "complete" | "partial" | "failed" | "canceled";
  reasonCode?: string;
  providerKey?: string;
  outputText?: string;
}

export interface ProviderInvocationPort {
  invoke(request: ProviderInvocationRequest): ProviderInvocationOutcome;
}

export interface TimelineEventEnvelope {
  runId: string;
  missionId: string;
  eventName: string;
  detail?: string;
  taskId?: string;
  handoffId?: string;
  source?: "executor" | "orchestrator";
  resultType?: "complete" | "partial" | "failed" | "canceled";
  reasonCode?: string;
}

export interface TelemetryEmitPort {
  emit(event: TimelineEventEnvelope): { delivered: boolean; eventName: string; runId: string };
}

export interface MessagingAckPort {
  acknowledge(runId: string): { acknowledged: boolean; runId: string };
}

export interface ExecutorLoopDependencies {
  provider: ProviderInvocationPort;
  telemetry?: TelemetryEmitPort;
  messaging?: MessagingAckPort;
}
