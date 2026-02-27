import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ThinkingPanel } from "./ThinkingPanel";

vi.mock("@/lib/store/aria-store", () => ({
  useARIAStore: vi.fn(),
}));
import { useARIAStore } from "@/lib/store/aria-store";

function setStore(state: { steps: unknown[]; panelStatus: string }) {
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
  });

  it('header shows "Failed" when panelStatus=failed', () => {
    setStore({ steps: [], panelStatus: "failed" });
    render(<ThinkingPanel />);
    expect(screen.getByText(/failed/i)).toBeTruthy();
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
});
