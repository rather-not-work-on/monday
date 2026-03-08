import type { ExecutorResult, MissionInput } from "@rather-not-work-on/contract-bindings";

export class ProviderClient {
  invoke(_request: MissionInput): ExecutorResult {
    return {
      resultType: "complete",
    };
  }
}
