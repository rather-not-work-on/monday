export type OperatorChannelKind = "slack_skill_cli" | "slack_skill_mcp" | "email_cli" | "email_mcp";

export type OperatorMessageClass =
  | "goal_intake_ack"
  | "status_update"
  | "decision_request"
  | "blocked_report"
  | "goal_completed";

export type DeliveryMode = "dry-run" | "apply";

export type OperatorDeliveryVerdict = "delivered" | "blocked" | "failed" | "dry_run";

export interface OperatorMessageTarget {
  channelKind: OperatorChannelKind;
  deliveryTarget: string;
  threadRef?: string;
}

export interface OperatorMessageEnvelope {
  messageClass: OperatorMessageClass;
  deliveryMode: DeliveryMode;
  goalKey: string;
  body: string;
  runId?: string;
  missionId?: string;
  taskId?: string;
  handoffId?: string;
  metadata?: Record<string, string>;
  target: OperatorMessageTarget;
}

export interface OperatorDeliveryReport {
  messageClass: OperatorMessageClass;
  goalKey: string;
  deliveryMode: DeliveryMode;
  channelKind: OperatorChannelKind;
  deliveryTarget: string;
  deliveryVerdict: OperatorDeliveryVerdict;
  deliveryTimestampUtc: string;
  deliveryIdempotencyKey: string;
  threadRef?: string;
}

export interface OperatorChannelPort {
  deliver(message: OperatorMessageEnvelope): OperatorDeliveryReport;
}

export interface GoalCompletionNotificationEnvelope extends OperatorMessageEnvelope {
  messageClass: "goal_completed";
  achievedAtUtc: string;
  summaryPath?: string;
}

export interface GoalCompletionNotificationPort {
  notifyCompletion(message: GoalCompletionNotificationEnvelope): OperatorDeliveryReport;
}
