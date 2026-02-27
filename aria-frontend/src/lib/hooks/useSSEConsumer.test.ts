import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useSSEConsumer } from "./useSSEConsumer";
import { useARIAStore, resetAllSlices } from "@/lib/store/aria-store";
import type { PlanStep } from "@/types/aria";

// Mock EventSource
class MockEventSource {
  static instance: MockEventSource | null = null;
  url: string;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    MockEventSource.instance = this;
  }
}

vi.stubGlobal("EventSource", MockEventSource);

// Helper to create a partial step that satisfies PlanStep for testing
const mockStep = (overrides: Partial<PlanStep>): PlanStep => ({
  step_index: 1,
  description: "Test Step",
  action: "click",
  target: null,
  value: null,
  confidence: 1.0,
  is_destructive: false,
  requires_user_input: false,
  user_input_reason: null,
  status: "pending",
  ...overrides,
});

describe("useSSEConsumer", () => {
  beforeEach(() => {
    useARIAStore.setState(resetAllSlices());
    vi.useFakeTimers();
    MockEventSource.instance = null;
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("does not open EventSource when sessionId is null", () => {
    renderHook(() => useSSEConsumer());
    expect(MockEventSource.instance).toBeNull();
  });

  it("opens EventSource when sessionId is set", () => {
    useARIAStore.setState({ sessionId: "test-session" });
    renderHook(() => useSSEConsumer());

    expect(MockEventSource.instance).not.toBeNull();
    expect(MockEventSource.instance?.url).toContain("/api/stream/test-session");
    expect(useARIAStore.getState().connectionStatus).toBe("connecting");
  });

  it("updates connectionStatus on open", () => {
    useARIAStore.setState({ sessionId: "test-session" });
    renderHook(() => useSSEConsumer());

    act(() => {
      MockEventSource.instance?.onopen?.(new Event("open"));
    });

    expect(useARIAStore.getState().connectionStatus).toBe("connected");
  });

  it("handles plan_ready event", () => {
    useARIAStore.setState({ sessionId: "test-session" });
    renderHook(() => useSSEConsumer());

    const payload = {
      task_summary: "Test Task",
      steps: [
        {
          step_index: 1,
          description: "Step 1",
          action: "click",
          status: "pending",
        },
      ],
    };

    act(() => {
      MockEventSource.instance?.onmessage?.({
        data: JSON.stringify({
          event_type: "plan_ready",
          session_id: "test-session",
          step_index: null,
          timestamp: "2024-01-01T00:00:00Z",
          payload,
        }),
      } as MessageEvent);
    });

    const state = useARIAStore.getState();
    expect(state.panelStatus).toBe("plan_ready");
    expect(state.taskSummary).toBe("Test Task");
    expect(state.steps).toHaveLength(1);
    expect(state.steps[0].status).toBe("pending");
  });

  it("handles step_start event", () => {
    useARIAStore.setState({
      sessionId: "test-session",
      steps: [mockStep({ step_index: 1, status: "pending" })],
    });
    renderHook(() => useSSEConsumer());

    act(() => {
      MockEventSource.instance?.onmessage?.({
        data: JSON.stringify({
          event_type: "step_start",
          session_id: "test-session",
          step_index: 1,
          timestamp: "2024-01-01T00:00:00Z",
          payload: {},
        }),
      } as MessageEvent);
    });

    expect(useARIAStore.getState().steps[0].status).toBe("active");
  });

  it("handles step_complete event", () => {
    useARIAStore.setState({
      sessionId: "test-session",
      steps: [mockStep({ step_index: 1, status: "active" })],
    });
    renderHook(() => useSSEConsumer());

    act(() => {
      MockEventSource.instance?.onmessage?.({
        data: JSON.stringify({
          event_type: "step_complete",
          session_id: "test-session",
          step_index: 1,
          timestamp: "2024-01-01T00:00:00Z",
          payload: { screenshot_url: "http://example.com/shot.png" },
        }),
      } as MessageEvent);
    });

    const step = useARIAStore.getState().steps[0];
    expect(step.status).toBe("complete");
    expect(step.screenshot_url).toBe("http://example.com/shot.png");
  });

  it("handles task_failed event", () => {
    useARIAStore.setState({ sessionId: "test-session" });
    renderHook(() => useSSEConsumer());

    act(() => {
      MockEventSource.instance?.onmessage?.({
        data: JSON.stringify({
          event_type: "task_failed",
          session_id: "test-session",
          step_index: null,
          timestamp: "2024-01-01T00:00:00Z",
          payload: { error: "Something went wrong" },
        }),
      } as MessageEvent);
    });

    expect(useARIAStore.getState().taskStatus).toBe("failed");
    expect(useARIAStore.getState().errorMessage).toBe("Something went wrong");
  });

  it("handles reconnection logic", () => {
    useARIAStore.setState({ sessionId: "test-session" });
    renderHook(() => useSSEConsumer());

    // First error
    act(() => {
      MockEventSource.instance?.onerror?.(new Event("error"));
    });

    expect(useARIAStore.getState().connectionStatus).toBe("reconnecting");
    expect(MockEventSource.instance?.close).toHaveBeenCalled();

    // Advance timer to trigger reconnect
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    // Should have created a new EventSource
    expect(useARIAStore.getState().connectionStatus).toBe("connecting");
  });

  it("stops reconnecting after max attempts", () => {
    useARIAStore.setState({ sessionId: "test-session" });
    renderHook(() => useSSEConsumer());

    // Simulate 6 errors (max is 5)
    for (let i = 1; i <= 6; i++) {
      act(() => {
        MockEventSource.instance?.onerror?.(new Event("error"));
      });
      if (i <= 5) {
        act(() => {
          vi.advanceTimersByTime(1000 * i);
        });
      }
    }

    expect(useARIAStore.getState().connectionStatus).toBe("error");
  });
});
