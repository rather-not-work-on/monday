import type { ExecutorResult, RunRef, RunStatus, TerminalOutcome } from "@rather-not-work-on/contract-bindings";

export interface RunLifecycleState {
  status: RunStatus;
  terminalOutcome?: TerminalOutcome;
}

export function deriveRunLifecycle(result: ExecutorResult): RunLifecycleState {
  switch (result.resultType) {
    case "complete":
      return { status: "terminal", terminalOutcome: "succeeded" };
    case "partial":
      return { status: "running" };
    case "failed":
      return { status: "blocked" };
    case "canceled":
      return { status: "terminal", terminalOutcome: "canceled" };
  }
}

export function buildRunRef(runId: string, result: ExecutorResult): RunRef {
  const lifecycle = deriveRunLifecycle(result);
  return {
    runId,
    status: lifecycle.status,
  };
}
