import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { TaskConfirmedBanner } from "./TaskConfirmedBanner";

vi.mock("@/lib/store/aria-store", () => ({
    useARIAStore: vi.fn(),
}));
import { useARIAStore } from "@/lib/store/aria-store";

function setStore(state: { sessionId: string | null; taskDescription: string }) {
    (useARIAStore as unknown as ReturnType<typeof vi.fn>).mockImplementation(
        () => state
    );
}

describe("TaskConfirmedBanner", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("renders nothing when sessionId is null", () => {
        setStore({ sessionId: null, taskDescription: "" });
        const { container } = render(<TaskConfirmedBanner />);
        expect(container.innerHTML).toBe("");
    });

    it("renders banner when sessionId exists", () => {
        setStore({ sessionId: "sess_abc", taskDescription: "Book a flight" });
        render(<TaskConfirmedBanner />);

        expect(screen.getByText("Task received:")).toBeInTheDocument();
        expect(screen.getByText("Book a flight")).toBeInTheDocument();
    });

    it("has task-confirmed-banner id for integration tests", () => {
        setStore({ sessionId: "sess_xyz", taskDescription: "Search the web" });
        render(<TaskConfirmedBanner />);

        const banner = document.getElementById("task-confirmed-banner");
        expect(banner).not.toBeNull();
    });

    it("displays task description in emerald mono font", () => {
        setStore({ sessionId: "sess_123", taskDescription: "Fill out a form" });
        render(<TaskConfirmedBanner />);

        const descriptionEl = screen.getByText("Fill out a form");
        expect(descriptionEl.className).toContain("font-mono");
        expect(descriptionEl.className).toContain("text-emerald-400");
    });

    it("has zinc-800 background with emerald border styling", () => {
        setStore({ sessionId: "sess_456", taskDescription: "Test" });
        render(<TaskConfirmedBanner />);

        const banner = document.getElementById("task-confirmed-banner");
        expect(banner?.className).toContain("bg-zinc-800");
        expect(banner?.className).toContain("border-emerald-800");
    });
});
