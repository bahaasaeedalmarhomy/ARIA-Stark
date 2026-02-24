import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import type { TaskStatus, SSEEvent } from "@/types/aria";

interface SessionSlice {
  sessionId: string | null;
  taskStatus: TaskStatus;
  taskDescription: string;
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
  immer((set) => ({
    // Session slice
    sessionId: null,
    taskStatus: "idle",
    taskDescription: "",
    // Voice slice
    voiceStatus: "idle",
    isVoiceConnecting: false,
    // Thinking panel slice
    steps: [],
    currentStepIndex: 0,
    taskSummary: "",
  }))
);
