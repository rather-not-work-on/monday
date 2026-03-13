import type {
  GoalCompletionNotificationEnvelope,
  GoalCompletionNotificationPort,
  OperatorDeliveryReport,
  OperatorDeliveryVerdict,
} from "@rather-not-work-on/contract-bindings";

const EMAIL_CHANNEL_KINDS = new Set(["email_cli", "email_mcp"]);

export interface GoalCompletionNotifierOptions {
  now?: () => string;
  deliveryVerdict?: OperatorDeliveryVerdict;
}

export function buildGoalCompletionIdempotencyKey(message: GoalCompletionNotificationEnvelope): string {
  return [
    message.goalKey,
    message.achievedAtUtc,
    message.target.channelKind,
    message.target.deliveryTarget,
  ].join(":");
}

export class GoalCompletionNotifier implements GoalCompletionNotificationPort {
  private readonly now: () => string;
  private readonly deliveryVerdict: OperatorDeliveryVerdict;

  constructor(options: GoalCompletionNotifierOptions = {}) {
    this.now = options.now ?? (() => new Date().toISOString());
    this.deliveryVerdict = options.deliveryVerdict ?? "delivered";
  }

  notifyCompletion(message: GoalCompletionNotificationEnvelope): OperatorDeliveryReport {
    if (!EMAIL_CHANNEL_KINDS.has(message.target.channelKind)) {
      throw new Error(`goal completion notifier requires email channel kind, got: ${message.target.channelKind}`);
    }

    return {
      messageClass: message.messageClass,
      goalKey: message.goalKey,
      deliveryMode: message.deliveryMode,
      channelKind: message.target.channelKind,
      deliveryTarget: message.target.deliveryTarget,
      deliveryVerdict: message.deliveryMode === "dry-run" ? "dry_run" : this.deliveryVerdict,
      deliveryTimestampUtc: this.now(),
      deliveryIdempotencyKey: buildGoalCompletionIdempotencyKey(message),
      threadRef: message.target.threadRef,
    };
  }
}
