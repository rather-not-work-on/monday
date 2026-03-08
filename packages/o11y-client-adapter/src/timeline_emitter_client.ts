export class TimelineEmitterClient {
  emit(eventName: string): { delivered: boolean; eventName: string } {
    return {
      delivered: true,
      eventName,
    };
  }
}
