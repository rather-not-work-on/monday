import type { MessagingAckPort } from "@rather-not-work-on/contract-bindings";

export class MessagingAdapter implements MessagingAckPort {
  acknowledge(runId: string): { acknowledged: boolean; runId: string } {
    return {
      acknowledged: true,
      runId,
    };
  }
}
