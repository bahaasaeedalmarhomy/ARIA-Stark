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
