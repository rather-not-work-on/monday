import type { TelemetryEmitPort, TimelineEventEnvelope } from "@rather-not-work-on/contract-bindings";

export class TimelineEmitterClient implements TelemetryEmitPort {
  emit(event: TimelineEventEnvelope): { delivered: boolean; eventName: string; runId: string } {
    return {
      delivered: true,
      eventName: event.eventName,
      runId: event.runId,
    };
  }
}
