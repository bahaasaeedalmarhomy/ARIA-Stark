// Shared ARIA TypeScript types — populated in Stories 1.4+
export type TaskStatus =
  | "idle"
  | "running"
  | "paused"
  | "awaiting_confirmation"
  | "awaiting_input"
  | "completed"
  | "failed";

export interface SSEEvent {
  event_type: string;
  session_id: string;
  step_index: number;
  timestamp: string;
  payload: Record<string, unknown>;
}

// Story 1.4: Task start API types
export interface StartTaskData {
  session_id: string;
  stream_url: string;
}

export interface StartTaskResponse {
  success: boolean;
  data: StartTaskData | null;
  error: { code: string; message: string } | null;
}
