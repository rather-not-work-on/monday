import type { ExecutorLoopDependencies } from "@rather-not-work-on/contract-bindings";
import { RalphLoopExecutor } from "@rather-not-work-on/executor-ralph-loop";
import { MessagingAdapter } from "@rather-not-work-on/messaging-adapter";
import { TimelineEmitterClient } from "@rather-not-work-on/o11y-client-adapter";
import { ProviderClient } from "@rather-not-work-on/provider-client-adapter";

export function buildDefaultExecutorDependencies(): ExecutorLoopDependencies {
  return {
    provider: new ProviderClient(),
    telemetry: new TimelineEmitterClient(),
    messaging: new MessagingAdapter(),
  };
}

export function buildDefaultExecutor(): RalphLoopExecutor {
  return new RalphLoopExecutor(buildDefaultExecutorDependencies());
}
