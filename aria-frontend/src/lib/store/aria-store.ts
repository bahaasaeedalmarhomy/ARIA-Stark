import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import type { TaskStatus, SSEEvent } from "@/types/aria";

interface SessionSlice {
  sessionId: string | null;
  taskStatus: TaskStatus;
  taskDescription: string;
  uid: string | null;       // Firebase Anonymous Auth uid
  idToken: string | null;  // JWT token for API Authorization header
  isSessionStarting: boolean; // tracks POST /api/task/start in-flight
}

interface VoiceSlice {
  voiceStatus: "idle" | "connecting" | "listening" | "speaking" | "paused" | "disconnected";
  isVoiceConnecting: boolean;
}

interface ThinkingPanelSlice {
  steps: SSEEvent[];
  currentStepIndex: number;
  taskSummary: string;
}

type ARIAStore = SessionSlice & VoiceSlice & ThinkingPanelSlice;

export const useARIAStore = create<ARIAStore>()(
  immer(() => ({
    // Session slice
    sessionId: null,
    taskStatus: "idle",
    taskDescription: "",
    uid: null,
    idToken: null,
    isSessionStarting: false,
    // Voice slice
    voiceStatus: "idle",
    isVoiceConnecting: false,
    // Thinking panel slice
    steps: [],
    currentStepIndex: 0,
    taskSummary: "",
  }))
);
