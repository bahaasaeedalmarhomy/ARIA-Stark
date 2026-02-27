"use client";

import { useEffect, useRef } from "react";
import { useARIAStore } from "@/lib/store/aria-store";
import type { SSEEvent, PlanStep, StepStatus } from "@/types/aria";

const MAX_RECONNECT_ATTEMPTS = 5;
const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8080";

export function useSSEConsumer() {
  const sessionId = useARIAStore((state) => state.sessionId);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!sessionId) return;

    const connect = () => {
      useARIAStore.setState({ connectionStatus: "connecting" });
      const es = new EventSource(`${BACKEND_URL}/api/stream/${sessionId}`);
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
        reconnectTimeoutRef.current = setTimeout(connect, 1000 * attempt);
      };
    };

    connect();

    return () => {
      eventSourceRef.current?.close();
      if (reconnectTimeoutRef.current)
        clearTimeout(reconnectTimeoutRef.current);
      reconnectAttemptsRef.current = 0;
    };
  }, [sessionId]);
}

function handleSSEEvent(event: SSEEvent) {
  switch (event.event_type) {
    case "plan_ready": {
      const payload = event.payload as {
        steps: PlanStep[];
        task_summary: string;
      };
      useARIAStore.setState({
        steps: payload.steps.map((s) => ({
          ...s,
          status: "pending" as StepStatus,
        })),
        taskSummary: payload.task_summary,
        panelStatus: "plan_ready",
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
      });
      break;
    }
    case "task_failed": {
      const payload = event.payload as { error?: string };
      useARIAStore.setState({
        taskStatus: "failed",
        errorMessage: payload.error ?? "Task failed",
      });
      break;
    }
  }
}
