export interface TaskExecutionEnvelope {
  runId: string;
  missionId: string;
  objective: string;
  taskId?: string;
  handoffId?: string;
}

export interface ProviderInvocationRequest {
  envelope: TaskExecutionEnvelope;
}

export interface ProviderInvocationOutcome {
  resultType: "complete" | "partial" | "failed" | "canceled";
  reasonCode?: string;
}

export interface ProviderInvocationPort {
  invoke(request: ProviderInvocationRequest): ProviderInvocationOutcome;
}

export interface TimelineEventEnvelope {
  runId: string;
  eventName: string;
  detail?: string;
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
