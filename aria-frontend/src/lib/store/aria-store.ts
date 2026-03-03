import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import type {
  TaskStatus,
  PlanStep,
  ThinkingPanelStatus,
  SSEConnectionStatus,
  FirestoreAuditStep,
} from "@/types/aria";

interface SessionSlice {
  sessionId: string | null;
  streamUrl: string | null;
  taskStatus: TaskStatus;
  taskDescription: string;
  uid: string | null; // Firebase Anonymous Auth uid
  idToken: string | null; // JWT token for API Authorization header
  isSessionStarting: boolean; // tracks POST /api/task/start in-flight
}

interface VoiceSlice {
  voiceStatus:
    | "idle"
    | "connecting"
    | "listening"
    | "speaking"
    | "paused"
    | "disconnected";
  isVoiceConnecting: boolean;
}

interface ThinkingPanelSlice {
  steps: PlanStep[];
  panelStatus: ThinkingPanelStatus;
  taskSummary: string;
  errorMessage: string | null;
  awaitingInputMessage: string | null;
  connectionStatus: SSEConnectionStatus;
  auditLog: FirestoreAuditStep[];
}

type ARIAStore = SessionSlice & VoiceSlice & ThinkingPanelSlice;

export const ARIA_INITIAL_STATE = {
  // Session slice
  sessionId: null,
  streamUrl: null,
  taskStatus: "idle" as TaskStatus,
  taskDescription: "",
  uid: null,
  idToken: null,
  isSessionStarting: false,
  // Voice slice
  voiceStatus: "idle" as const,
  isVoiceConnecting: false,
  // Thinking panel slice
  steps: [],
  panelStatus: "idle" as ThinkingPanelStatus,
  taskSummary: "",
  errorMessage: null,
  awaitingInputMessage: null,
  connectionStatus: "disconnected" as SSEConnectionStatus,
  auditLog: [],
};

export const resetAllSlices = () => ARIA_INITIAL_STATE;

export const useARIAStore = create<ARIAStore>()(
  immer(() => ARIA_INITIAL_STATE)
);
