import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ThinkingPanel } from "./ThinkingPanel";

vi.mock("@/lib/hooks/useFirestoreSession", () => ({
  useFirestoreSession: vi.fn(),
}));

vi.mock("@/lib/store/aria-store", () => ({
  useARIAStore: vi.fn(),
}));
import { useARIAStore } from "@/lib/store/aria-store";

function setStore(state: {
  steps: unknown[];
  panelStatus: string;
  taskSummary?: string;
  taskStatus?: string;
  awaitingInputMessage?: string | null;
  sessionId?: string | null;
  auditLog?: unknown[];
}) {
  const defaults = {
    taskStatus: "idle",
    awaitingInputMessage: null,
    sessionId: null,
    auditLog: [],
    taskSummary: "",
    ...state,
  };
  (useARIAStore as unknown as ReturnType<typeof vi.fn>).mockImplementation(
    (selector: (state: unknown) => unknown) => selector(defaults)
  );
}

describe("ThinkingPanel", () => {
  const scrollIntoViewMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    scrollIntoViewMock.mockClear();
    Element.prototype.scrollIntoView = scrollIntoViewMock;
    setStore({ steps: [], panelStatus: "idle" });
  });

  it('renders "Waiting for task…" when idle and no steps', () => {
    render(<ThinkingPanel />);
    expect(screen.getByText(/waiting for task/i)).toBeTruthy();
  });

  it('renders "Planning…" when planning and no steps', () => {
    setStore({ steps: [], panelStatus: "planning" });
    render(<ThinkingPanel />);
    expect(screen.getByText(/planning…/i)).toBeTruthy();
  });

  it("renders one StepItem per step", () => {
    setStore({
      steps: [
        { step_index: 0, description: "Step A", status: "pending", confidence: 0.6 },
        { step_index: 1, description: "Step B", status: "active", confidence: 0.9 },
        { step_index: 2, description: "Step C", status: "complete", confidence: 0.7 },
      ],
      panelStatus: "plan_ready",
    });
    render(<ThinkingPanel />);
    expect(screen.getByText("Step A")).toBeTruthy();
    expect(screen.getByText("Step B")).toBeTruthy();
    expect(screen.getByText("Step C")).toBeTruthy();
  });

  it('header shows "Done" when panelStatus=complete', () => {
    setStore({ steps: [], panelStatus: "complete" });
    render(<ThinkingPanel />);
    expect(screen.getByText(/done/i)).toBeTruthy();
    const header = screen.getByRole("status");
    expect((header as HTMLElement).className).toContain("text-confidence-high");
  });

  it('header shows "Failed" when panelStatus=failed', () => {
    setStore({ steps: [], panelStatus: "failed" });
    render(<ThinkingPanel />);
    expect(screen.getByText(/failed/i)).toBeTruthy();
    const header = screen.getByRole("status");
    expect((header as HTMLElement).className).toContain("text-confidence-low");
  });

  it("scrolls active step into view", () => {
    setStore({
      steps: [
        { step_index: 0, description: "Step A", status: "complete", confidence: 0.9 },
        { step_index: 1, description: "Step B", status: "active", confidence: 0.8 },
      ],
      panelStatus: "executing",
    });

    render(<ThinkingPanel />);
    
    // The effect should run and call scrollIntoView on the active step element
    expect(scrollIntoViewMock).toHaveBeenCalledWith({
      behavior: "smooth",
      block: "nearest",
    });
  });

  it("applies animate-step-enter class and correct delay to each step li", () => {
    const steps = [
      { step_index: 0, description: "Step A", status: "pending", confidence: 0.9 },
      { step_index: 1, description: "Step B", status: "pending", confidence: 0.7 },
      { step_index: 2, description: "Step C", status: "pending", confidence: 0.3 },
    ];
    setStore({ steps, panelStatus: "plan_ready", taskSummary: "" });
    const { container } = render(<ThinkingPanel />);
    const listItems = container.querySelectorAll("li");
    expect(listItems[0].className).toContain("animate-step-enter");
    expect((listItems[0] as HTMLElement).style.animationDelay).toBe("0ms");
    expect((listItems[1] as HTMLElement).style.animationDelay).toBe("60ms");
    expect((listItems[2] as HTMLElement).style.animationDelay).toBe("120ms");
  });

  it("shows task summary when taskSummary is non-empty", () => {
    setStore({
      steps: [{ step_index: 0, description: "Step A", status: "pending", confidence: 0.6 }],
      panelStatus: "plan_ready",
      taskSummary: "Book a flight to Paris",
    });
    const { container } = render(<ThinkingPanel />);
    expect(screen.getByText(/Task understood:/i)).toBeTruthy();
    expect(screen.getByText(/Book a flight to Paris/)).toBeTruthy();
    const summary = container.querySelector("#task-summary");
    const list = container.querySelector("ul");
    expect(summary).not.toBeNull();
    expect((list as HTMLElement).getAttribute("aria-describedby")).toBe("task-summary");
  });

  it("does not show task summary when taskSummary is empty", () => {
    setStore({ steps: [], panelStatus: "idle", taskSummary: "" });
    render(<ThinkingPanel />);
    expect(screen.queryByText(/Task understood:/i)).toBeNull();
  });

  it("renders audit log section when panelStatus=complete and auditLog is non-empty", () => {
    setStore({
      steps: [],
      panelStatus: "complete",
      auditLog: [
        {
          step_index: 0,
          description: "Navigate to site",
          action_type: "navigate",
          result: "done",
          screenshot_url: "https://storage.googleapis.com/bucket/step0.png",
          confidence: 0.9,
          timestamp: "2026-03-03T14:22:33.456Z",
          status: "complete",
        },
      ],
    });
    render(<ThinkingPanel />);

    const section = screen.getByTestId("audit-log-section");
    expect(section).toBeTruthy();
    expect(screen.getByText(/1 step recorded/i)).toBeTruthy();
    expect(screen.getByText("Navigate to site")).toBeTruthy();
    expect(screen.getByText("[screenshot]")).toBeTruthy();
  });

  it("does not render audit log section when panelStatus is not complete", () => {
    setStore({
      steps: [],
      panelStatus: "executing",
      auditLog: [
        {
          step_index: 0,
          description: "Navigate",
          action_type: "navigate",
          result: "done",
          screenshot_url: null,
          confidence: 0.9,
          timestamp: "2026-03-03T14:22:33.456Z",
          status: "complete",
        },
      ],
    });
    render(<ThinkingPanel />);
    expect(screen.queryByTestId("audit-log-section")).toBeNull();
  });

  it("does not render audit log section when auditLog is empty", () => {
    setStore({ steps: [], panelStatus: "complete", auditLog: [] });
    render(<ThinkingPanel />);
    expect(screen.queryByTestId("audit-log-section")).toBeNull();
  });

  it("does not render [screenshot] badge when screenshot_url is null", () => {
    setStore({
      steps: [],
      panelStatus: "complete",
      auditLog: [
        {
          step_index: 0,
          description: "Click button",
          action_type: "click",
          result: "done",
          screenshot_url: null,
          confidence: 0.8,
          timestamp: "2026-03-03T14:22:33.456Z",
          status: "complete",
        },
      ],
    });
    render(<ThinkingPanel />);
    expect(screen.getByTestId("audit-log-section")).toBeTruthy();
    expect(screen.queryByText("[screenshot]")).toBeNull();
  });
});
