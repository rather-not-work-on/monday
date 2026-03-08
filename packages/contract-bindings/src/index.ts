export type RunStatus = "queued" | "running" | "blocked" | "terminal";

export type TerminalOutcome = "succeeded" | "failed" | "canceled";

export type ResultType = "complete" | "partial" | "failed" | "canceled";

export interface MissionInput {
  missionId: string;
  objective: string;
}

export interface RunRef {
  runId: string;
  status: RunStatus;
}

export interface TaskPlan {
  tasks: string[];
}

export interface SubtaskHandoff {
  handoffId: string;
  taskId: string;
}

export interface ExecutorResult {
  resultType: ResultType;
}
