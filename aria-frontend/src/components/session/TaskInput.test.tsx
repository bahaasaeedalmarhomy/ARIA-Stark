import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";
import { TaskConfirmedBanner } from "@/components/session/TaskConfirmedBanner";
import { TaskInput } from "@/components/session/TaskInput";
import { useARIAStore } from "@/lib/store/aria-store";
import { startTask } from "@/lib/api/task";

vi.mock("@/lib/api/task", () => ({
    startTask: vi.fn(),
}));

function renderSessionUI() {
    return render(
        <div>
            <TaskConfirmedBanner />
            <TaskInput />
        </div>
    );
}

beforeEach(() => {
    useARIAStore.setState({
        sessionId: null,
        taskStatus: "idle",
        taskDescription: "",
        uid: "uid_123",
        idToken: "token_123",
        isSessionStarting: false,
    });
});

afterEach(() => {
    vi.clearAllMocks();
});

describe("TaskInput", () => {
    it("renders textarea and Start Task button", () => {
        renderSessionUI();

        expect(
            screen.getByPlaceholderText("Describe a task for ARIA...")
        ).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Start Task" })).toBeEnabled();
    });

    it("shows loading state while API is in-flight", async () => {
        vi.mocked(startTask).mockReturnValue(new Promise(() => {}) as never);

        renderSessionUI();

        fireEvent.change(screen.getByPlaceholderText("Describe a task for ARIA..."), {
            target: { value: "Do something" },
        });
        fireEvent.click(screen.getByRole("button", { name: "Start Task" }));

        expect(screen.getByRole("button", { name: "Starting..." })).toBeDisabled();
        expect(document.querySelector(".animate-spin")).not.toBeNull();
    });

    it("on success sets sessionId and shows confirmed banner", async () => {
        vi.mocked(startTask).mockResolvedValue({
            success: true,
            data: { session_id: "sess_abc", stream_url: "/api/stream/sess_abc" },
            error: null,
        });

        renderSessionUI();

        fireEvent.change(screen.getByPlaceholderText("Describe a task for ARIA..."), {
            target: { value: "Book a flight" },
        });
        fireEvent.click(screen.getByRole("button", { name: "Start Task" }));

        await waitFor(() =>
            expect(useARIAStore.getState().sessionId).toBe("sess_abc")
        );
        expect(useARIAStore.getState().taskStatus).toBe("running");
        expect(screen.getByText("Task received:")).toBeInTheDocument();
        const banner = document.getElementById("task-confirmed-banner");
        expect(banner).not.toBeNull();
        expect(within(banner as HTMLElement).getByText("Book a flight")).toBeInTheDocument();
    });

    it("on error renders error message and re-enables button", async () => {
        vi.mocked(startTask).mockResolvedValue({
            success: false,
            data: null,
            error: { code: "UNAUTHORIZED", message: "Invalid token" },
        });

        renderSessionUI();

        fireEvent.change(screen.getByPlaceholderText("Describe a task for ARIA..."), {
            target: { value: "Do something" },
        });
        fireEvent.click(screen.getByRole("button", { name: "Start Task" }));

        await waitFor(() =>
            expect(screen.getByText("Invalid token")).toBeInTheDocument()
        );

        expect(document.getElementById("task-error")).not.toBeNull();
        expect(screen.getByRole("button", { name: "Start Task" })).toBeEnabled();
        expect(useARIAStore.getState().sessionId).toBeNull();
    });

    it("shows confirmation prompt when taskStatus is not idle", async () => {
        useARIAStore.setState({ taskStatus: "running" });
        vi.mocked(startTask).mockResolvedValue({
            success: true,
            data: { session_id: "sess_new", stream_url: "/api/stream/sess_new" },
            error: null,
        });

        renderSessionUI();

        fireEvent.change(screen.getByPlaceholderText("Describe a task for ARIA..."), {
            target: { value: "New task" },
        });
        fireEvent.click(screen.getByRole("button", { name: "Start Task" }));

        expect(
            screen.getByText("Cancel current task and start a new one?")
        ).toBeInTheDocument();
        expect(startTask).not.toHaveBeenCalled();

        fireEvent.click(screen.getByRole("button", { name: "Confirm" }));

        await waitFor(() =>
            expect(useARIAStore.getState().sessionId).toBe("sess_new")
        );
        expect(startTask).toHaveBeenCalledTimes(1);
    });
});
