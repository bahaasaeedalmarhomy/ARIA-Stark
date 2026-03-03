import { renderHook, cleanup, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useARIAStore, resetAllSlices } from "@/lib/store/aria-store";

// vi.mock is hoisted  factory must NOT reference top-level variables
vi.mock("firebase/firestore", () => ({
  getFirestore: vi.fn(() => ({})),
  doc: vi.fn(() => ({ id: "mock-doc-ref" })),
  onSnapshot: vi.fn(() => vi.fn()), // default: returns a no-op unsubscribe
}));

vi.mock("@/lib/firebase", () => ({
  app: {},
}));

// Import mocked functions AFTER vi.mock declarations
import { onSnapshot, doc } from "firebase/firestore";
// Import hook AFTER mocks
import { useFirestoreSession } from "./useFirestoreSession";

const mockOnSnapshot = vi.mocked(onSnapshot);
const mockDoc = vi.mocked(doc);

describe("useFirestoreSession", () => {
  beforeEach(() => {
    useARIAStore.setState(resetAllSlices());
    vi.clearAllMocks();
    // Reset defaults after clearAllMocks
    mockDoc.mockReturnValue({ id: "mock-doc-ref" } as ReturnType<typeof doc>);
    mockOnSnapshot.mockReturnValue(vi.fn() as ReturnType<typeof onSnapshot>);
  });

  afterEach(() => {
    cleanup();
  });

  it("does not subscribe when sessionId is null", () => {
    renderHook(() => useFirestoreSession());
    expect(mockOnSnapshot).not.toHaveBeenCalled();
  });

  it("subscribes to sessions/{sessionId} when sessionId is set", () => {
    useARIAStore.setState({ sessionId: "sess_123" });
    renderHook(() => useFirestoreSession());

    expect(mockDoc).toHaveBeenCalledWith(
      expect.anything(),
      "sessions",
      "sess_123"
    );
    expect(mockOnSnapshot).toHaveBeenCalledTimes(1);
  });

  it("populates auditLog from snapshot data", () => {
    useARIAStore.setState({ sessionId: "sess_456" });

    const mockStep = {
      step_index: 0,
      description: "Navigate to site",
      action_type: "navigate",
      result: "done",
      screenshot_url: null,
      confidence: 0.9,
      timestamp: "2026-03-03T14:22:33.456Z",
      status: "complete" as const,
    };

    mockOnSnapshot.mockImplementation((_ref, successCb) => {
      const cb = successCb as (snap: unknown) => void;
      cb({
        exists: () => true,
        data: () => ({ steps: [mockStep] }),
      });
      return vi.fn() as ReturnType<typeof onSnapshot>;
    });

    act(() => {
      renderHook(() => useFirestoreSession());
    });

    const { auditLog } = useARIAStore.getState();
    expect(auditLog).toHaveLength(1);
    expect(auditLog[0].step_index).toBe(0);
    expect(auditLog[0].description).toBe("Navigate to site");
  });

  it("handles snapshot that does not exist without crashing", () => {
    useARIAStore.setState({ sessionId: "sess_789" });

    mockOnSnapshot.mockImplementation((_ref, successCb) => {
      const cb = successCb as (snap: unknown) => void;
      cb({ exists: () => false, data: () => null });
      return vi.fn() as ReturnType<typeof onSnapshot>;
    });

    renderHook(() => useFirestoreSession());

    const { auditLog } = useARIAStore.getState();
    expect(auditLog).toHaveLength(0);
  });

  it("calls unsubscribe on cleanup", () => {
    useARIAStore.setState({ sessionId: "sess_cleanup" });
    const mockUnsub = vi.fn();
    mockOnSnapshot.mockReturnValue(mockUnsub as unknown as ReturnType<typeof onSnapshot>);

    const { unmount } = renderHook(() => useFirestoreSession());

    expect(mockOnSnapshot).toHaveBeenCalledTimes(1);

    unmount();

    expect(mockUnsub).toHaveBeenCalledTimes(1);
  });

  it("logs warning on snapshot error", () => {
    useARIAStore.setState({ sessionId: "sess_err" });

    const consoleSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    mockOnSnapshot.mockImplementation((_ref, _successCb, errorCb) => {
      const cb = errorCb as (err: unknown) => void;
      cb(new Error("Permission denied"));
      return vi.fn() as ReturnType<typeof onSnapshot>;
    });

    renderHook(() => useFirestoreSession());

    expect(consoleSpy).toHaveBeenCalledWith(
      expect.stringContaining("[useFirestoreSession]"),
      expect.any(Error)
    );

    consoleSpy.mockRestore();
  });
});
