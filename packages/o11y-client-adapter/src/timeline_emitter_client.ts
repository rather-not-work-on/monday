import type { TelemetryEmitPort, TimelineEventEnvelope } from "@rather-not-work-on/contract-bindings";

export interface TimelineEmitterProfile {
  runtimeProfileName: string;
  telemetryBaseUrl: string;
  executionMode?: string;
}

export interface TimelineEmitterClientOptions {
  profile?: TimelineEmitterProfile;
}

export function normalizeTimelineEvent(event: TimelineEventEnvelope): TimelineEventEnvelope {
  return {
    ...event,
    runId: event.runId.trim(),
    missionId: event.missionId.trim(),
    eventName: event.eventName.trim() || "executor.unknown",
    detail: event.detail?.trim() || undefined,
    reasonCode: event.reasonCode?.trim() || undefined,
    source: event.source ?? "executor",
  };
}

export class TimelineEmitterClient implements TelemetryEmitPort {
  constructor(private readonly options: TimelineEmitterClientOptions = {}) {}

  emit(event: TimelineEventEnvelope): { delivered: boolean; eventName: string; runId: string } {
    const normalizedEvent = normalizeTimelineEvent(event);

    return {
      delivered: normalizedEvent.runId.length > 0 && (!this.options.profile || this.options.profile.telemetryBaseUrl.length > 0),
      eventName: normalizedEvent.eventName,
      runId: normalizedEvent.runId,
    };
  }
}
