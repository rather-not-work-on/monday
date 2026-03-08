import type { RunRef } from "@rather-not-work-on/contract-bindings";

export class MessagingAdapter {
  acknowledge(run: RunRef): { acknowledged: boolean; runId: string } {
    return {
      acknowledged: true,
      runId: run.runId,
    };
  }
}
