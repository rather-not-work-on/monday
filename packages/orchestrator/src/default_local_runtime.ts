import type { ExecutorLoopDependencies, MessagingAckPort } from "@rather-not-work-on/contract-bindings";
import { RalphLoopExecutor } from "@rather-not-work-on/executor-ralph-loop";
import { MessagingAdapter } from "@rather-not-work-on/messaging-adapter";
import {
  TimelineEmitterClient,
  type TimelineEmitterClientOptions,
  type TimelineEmitterProfile,
} from "@rather-not-work-on/o11y-client-adapter";
import {
  ProviderClient,
  type ProviderClientOptions,
  type ProviderClientProfile,
} from "@rather-not-work-on/provider-client-adapter";

export interface LocalRuntimeProfileSource {
  execution_mode: string;
  litellm_base_url: string;
  langfuse_host: string;
  nanoclaw_endpoint?: string;
}

export interface LocalRuntimeProfileCatalog {
  active_profile?: string;
  profiles: Record<string, LocalRuntimeProfileSource>;
}

export interface LocalRuntimeProfile {
  profileName: string;
  executionMode: string;
  providerBaseUrl: string;
  telemetryBaseUrl: string;
  nanoclawEndpoint?: string;
}

export interface DefaultLocalRuntimeOptions {
  profile: LocalRuntimeProfile;
  provider?: ExecutorLoopDependencies["provider"];
  telemetry?: ExecutorLoopDependencies["telemetry"];
  messaging?: MessagingAckPort;
}

function buildProviderProfile(profile: LocalRuntimeProfile): ProviderClientProfile {
  return {
    runtimeProfileName: profile.profileName,
    providerBaseUrl: profile.providerBaseUrl,
    executionMode: profile.executionMode,
  };
}

function buildTelemetryProfile(profile: LocalRuntimeProfile): TimelineEmitterProfile {
  return {
    runtimeProfileName: profile.profileName,
    telemetryBaseUrl: profile.telemetryBaseUrl,
    executionMode: profile.executionMode,
  };
}

export function resolveLocalRuntimeProfile(
  catalog: LocalRuntimeProfileCatalog,
  requestedProfileName = catalog.active_profile,
): LocalRuntimeProfile {
  if (!requestedProfileName) {
    throw new Error("runtime profile name is required");
  }

  const rawProfile = catalog.profiles[requestedProfileName];
  if (!rawProfile) {
    throw new Error(`runtime profile '${requestedProfileName}' is not defined`);
  }

  return {
    profileName: requestedProfileName,
    executionMode: rawProfile.execution_mode,
    providerBaseUrl: rawProfile.litellm_base_url,
    telemetryBaseUrl: rawProfile.langfuse_host,
    nanoclawEndpoint: rawProfile.nanoclaw_endpoint,
  };
}

export function buildDefaultLocalRuntimeDependencies(options: DefaultLocalRuntimeOptions): ExecutorLoopDependencies {
  const providerOptions: ProviderClientOptions = { profile: buildProviderProfile(options.profile) };
  const telemetryOptions: TimelineEmitterClientOptions = { profile: buildTelemetryProfile(options.profile) };

  return {
    provider: options.provider ?? new ProviderClient(providerOptions),
    telemetry: options.telemetry ?? new TimelineEmitterClient(telemetryOptions),
    messaging: options.messaging ?? new MessagingAdapter(),
  };
}

export function buildDefaultLocalExecutor(options: DefaultLocalRuntimeOptions): RalphLoopExecutor {
  return new RalphLoopExecutor(buildDefaultLocalRuntimeDependencies(options));
}
