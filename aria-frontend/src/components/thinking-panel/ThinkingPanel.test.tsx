import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ThinkingPanel } from "./ThinkingPanel";

vi.mock("@/lib/store/aria-store", () => ({
  useARIAStore: vi.fn(),
}));
import { useARIAStore } from "@/lib/store/aria-store";

function setStore(state: { steps: unknown[]; panelStatus: string; taskSummary?: string }) {
  (useARIAStore as unknown as ReturnType<typeof vi.fn>).mockImplementation(
    (selector: (state: unknown) => unknown) => selector(state)
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
});
