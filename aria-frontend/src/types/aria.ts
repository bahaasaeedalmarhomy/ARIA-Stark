// Shared ARIA TypeScript types — populated in Stories 1.4+
export type TaskStatus =
  | "idle"
  | "running"
  | "paused"
  | "awaiting_confirmation"
  | "awaiting_input"
  | "completed"
  | "failed";

export type StepStatus = "pending" | "active" | "complete" | "error";

export type ThinkingPanelStatus =
  | "idle"
  | "planning"
  | "plan_ready"
  | "executing"
  | "awaiting_input"
  | "complete"
  | "failed";

export type SSEConnectionStatus =
  | "disconnected"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "error";

export interface PlanStep {
  step_index: number;
  description: string;
  action: "navigate" | "click" | "type" | "scroll" | "screenshot" | "wait";
  target: string | null;
  value: string | null;
  confidence: number;
  is_destructive: boolean;
  requires_user_input: boolean;
  user_input_reason: string | null;
  // Frontend-only fields:
  status: StepStatus;
  screenshot_url?: string | null;
}

export interface SSEEvent {
  event_type: string;
  session_id: string;
  step_index: number | null;
  timestamp: string;
  payload: Record<string, unknown>;
}

export interface FirestoreAuditStep {
  step_index: number;
  action_type: string | null;
  description: string;
  result: string;
  screenshot_url: string | null;
  confidence: number;
  timestamp: string; // ISO 8601 UTC e.g. "2026-03-03T14:22:33.456Z"
  status: "complete" | "error";
}

// Story 1.4: Task start API types
export interface StartTaskData {
  session_id: string;
  stream_url: string;
  step_plan?: {
    task_summary: string;
    steps: PlanStep[];
  };
}

export interface StartTaskResponse {
  success: boolean;
  data: StartTaskData | null;
  error: { code: string; message: string } | null;
}
