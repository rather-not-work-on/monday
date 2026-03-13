import type {
  OperatorChannelPort,
  OperatorDeliveryReport,
  OperatorDeliveryVerdict,
  OperatorMessageEnvelope,
} from "@rather-not-work-on/contract-bindings";

export interface OperatorChannelTransportResult {
  deliveryVerdict: OperatorDeliveryVerdict;
  deliveryTimestampUtc?: string;
  deliveryIdempotencyKey?: string;
  threadRef?: string;
}

export interface OperatorChannelTransport {
  deliver(message: OperatorMessageEnvelope): OperatorChannelTransportResult;
}

export interface OperatorChannelAdapterOptions {
  transport?: OperatorChannelTransport;
  now?: () => string;
}

export function buildOperatorDeliveryIdempotencyKey(message: OperatorMessageEnvelope): string {
  return [
    message.messageClass,
    message.goalKey,
    message.target.channelKind,
    message.target.deliveryTarget,
    message.runId ?? "-",
    message.taskId ?? "-",
  ].join(":");
}

export class DryRunOperatorChannelTransport implements OperatorChannelTransport {
  deliver(): OperatorChannelTransportResult {
    return {
      deliveryVerdict: "dry_run",
    };
  }
}

export class OperatorChannelAdapter implements OperatorChannelPort {
  private readonly transport: OperatorChannelTransport;
  private readonly now: () => string;

  constructor(options: OperatorChannelAdapterOptions = {}) {
    this.transport = options.transport ?? new DryRunOperatorChannelTransport();
    this.now = options.now ?? (() => new Date().toISOString());
  }

  deliver(message: OperatorMessageEnvelope): OperatorDeliveryReport {
    const transportResult = this.transport.deliver(message);
    return {
      messageClass: message.messageClass,
      goalKey: message.goalKey,
      deliveryMode: message.deliveryMode,
      channelKind: message.target.channelKind,
      deliveryTarget: message.target.deliveryTarget,
      deliveryVerdict: message.deliveryMode === "dry-run" ? "dry_run" : transportResult.deliveryVerdict,
      deliveryTimestampUtc: transportResult.deliveryTimestampUtc ?? this.now(),
      deliveryIdempotencyKey:
        transportResult.deliveryIdempotencyKey ?? buildOperatorDeliveryIdempotencyKey(message),
      threadRef: transportResult.threadRef ?? message.target.threadRef,
    };
  }
}
