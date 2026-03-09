import type {
  ExecutorLoopDependencies,
  ExecutorResult,
  MissionInput,
  SubtaskHandoff,
} from "@rather-not-work-on/contract-bindings";
import { buildProviderRequest } from "@rather-not-work-on/provider-client-adapter";

import { buildExecutorEvent } from "./event_policy.js";

export class RalphLoopExecutor {
  constructor(private readonly dependencies: ExecutorLoopDependencies) {}

  execute(context: MissionInput, handoff?: SubtaskHandoff): ExecutorResult {
    const providerRequest = buildProviderRequest({
      mission: context,
      handoff,
    });
    const providerOutcome = this.dependencies.provider.invoke(providerRequest);

    this.dependencies.telemetry?.emit(buildExecutorEvent(context, providerOutcome, handoff));

    this.dependencies.messaging?.acknowledge(providerRequest.envelope.runId);

    return providerOutcome;
  }

  cancel(runId: string, reason: string): { runId: string; canceled: boolean; reason: string } {
    return {
      runId,
      canceled: true,
      reason,
    };
  }
}
