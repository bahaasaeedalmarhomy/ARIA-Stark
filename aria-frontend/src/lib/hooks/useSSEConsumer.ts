"use client";

import { useEffect, useRef } from "react";
import { useARIAStore } from "@/lib/store/aria-store";
import type { SSEEvent, PlanStep, StepStatus } from "@/types/aria";

import { BACKEND_URL } from "@/lib/constants";

const MAX_RECONNECT_ATTEMPTS = 5;

export function useSSEConsumer() {
  const sessionId = useARIAStore((state) => state.sessionId);
  const streamUrl = useARIAStore((state) => state.streamUrl);
  const idToken = useARIAStore((state) => state.idToken);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!sessionId && !streamUrl) return;

    const connect = () => {
      useARIAStore.setState({ connectionStatus: "connecting" });
      const base =
        streamUrl
          ? (streamUrl.startsWith("http") ? streamUrl : `${BACKEND_URL}${streamUrl}`)
          : `${BACKEND_URL}/api/stream/${sessionId}`;
      const tokenParam = idToken ? `token=${encodeURIComponent(idToken)}` : "";
      const separator = base.includes("?") ? "&" : "?";
      const url = tokenParam ? `${base}${separator}${tokenParam}` : base;
      const es = new EventSource(url);
      eventSourceRef.current = es;

      es.onopen = () => {
        reconnectAttemptsRef.current = 0;
        useARIAStore.setState({ connectionStatus: "connected" });
      };

      es.onmessage = (event) => {
        try {
          const sseEvent: SSEEvent = JSON.parse(event.data);
          handleSSEEvent(sseEvent);
        } catch {
          // Non-JSON frame (e.g., keepalive comment) — ignore silently
        }
      };

      es.onerror = () => {
        es.close();
        const attempt = ++reconnectAttemptsRef.current;
        if (attempt > MAX_RECONNECT_ATTEMPTS) {
          useARIAStore.setState({ connectionStatus: "error" });
          return;
        }
        useARIAStore.setState({ connectionStatus: "reconnecting" });
        reconnectTimeoutRef.current = setTimeout(connect, 1000);
      };
    };

    connect();

    return () => {
      eventSourceRef.current?.close();
      if (reconnectTimeoutRef.current)
        clearTimeout(reconnectTimeoutRef.current);
      reconnectAttemptsRef.current = 0;
    };
  }, [sessionId, streamUrl, idToken]);
}

function handleSSEEvent(event: SSEEvent) {
  switch (event.event_type) {
    case "plan_ready": {
      const payload = event.payload as {
        steps: PlanStep[];
        task_summary: string;
        is_replan?: boolean;
      };
      useARIAStore.setState((state) => {
        state.steps = payload.steps.map((s) => ({
          ...s,
          status: "pending" as StepStatus,
        }));
        state.taskSummary = payload.task_summary;
        state.panelStatus = "plan_ready";
        if (payload.is_replan) {
          state.taskStatus = "running";
          state.voiceStatus = "listening"; // clear paused state — ARIA back to ambient listening
        }
      });
      break;
    }
    case "step_start": {
      useARIAStore.setState((state) => {
        const step = state.steps.find((s) => s.step_index === event.step_index);
        if (step) step.status = "active";
      });
      break;
    }
    case "step_planned": {
      const payload = event.payload as { step: PlanStep };
      useARIAStore.setState((state) => {
        // Avoid duplicates if reconnect triggers replays
        const exists = state.steps.some((s) => s.step_index === payload.step.step_index);
        if (!exists) {
          state.steps.push({ ...payload.step, status: "pending" as StepStatus });
          state.panelStatus = "plan_ready";
        }
      });
      break;
    }
    case "step_complete": {
      const payload = event.payload as { screenshot_url?: string };
      useARIAStore.setState((state) => {
        const step = state.steps.find((s) => s.step_index === event.step_index);
        if (step) {
          step.status = "complete";
          if (payload.screenshot_url)
            step.screenshot_url = payload.screenshot_url;
        }
      });
      break;
    }
    case "step_error": {
      useARIAStore.setState((state) => {
        const step = state.steps.find((s) => s.step_index === event.step_index);
        if (step) step.status = "error";
      });
      break;
    }
    case "task_complete": {
      useARIAStore.setState({
        taskStatus: "completed",
        panelStatus: "complete",
        awaitingInputMessage: null,
      });
      break;
    }
    case "task_failed": {
      const payload = event.payload as { error?: string; reason?: string };
      const isCancelled = payload.reason === "user_cancelled";
      useARIAStore.setState({
        taskStatus: "failed",
        panelStatus: "failed",
        errorMessage: isCancelled
          ? "Task cancelled by user"
          : (payload.error ?? payload.reason ?? "Task failed"),
        awaitingInputMessage: null,
      });
      break;
    }
    case "awaiting_input": {
      const payload = event.payload as { reason?: string; message?: string };
      useARIAStore.setState({
        taskStatus: "awaiting_input",
        panelStatus: "awaiting_input",
        awaitingInputMessage:
          payload.message ?? "ARIA needs your input to continue",
      });
      break;
    }
    case "task_paused": {
      // Voice barge-in pause — mark active step as paused and update app state
      useARIAStore.setState((state) => {
        const activeStep = state.steps.find((s) => s.status === "active");
        if (activeStep) activeStep.status = "paused";
        state.taskStatus = "paused";
        state.panelStatus = "paused";
        state.voiceStatus = "paused"; // triggers BargeInPulse + violet waveform (Story 4.3)
      });
      break;
    }
  }
}