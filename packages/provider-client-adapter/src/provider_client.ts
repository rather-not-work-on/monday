import type {
  ProviderInvocationOutcome,
  ProviderInvocationPort,
  ProviderInvocationRequest,
} from "@rather-not-work-on/contract-bindings";

export class ProviderClient implements ProviderInvocationPort {
  invoke(_request: ProviderInvocationRequest): ProviderInvocationOutcome {
    return {
      resultType: "complete",
    };
  }
}
