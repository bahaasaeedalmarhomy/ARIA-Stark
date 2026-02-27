import { describe, it, expect, beforeEach } from "vitest";
import { useARIAStore, resetAllSlices, ARIA_INITIAL_STATE } from "./aria-store";

describe("aria-store", () => {
    beforeEach(() => {
        useARIAStore.setState(resetAllSlices());
    });

    // ── Initial State ────────────────────────────────────────────────────

    it("has correct initial session slice", () => {
        const state = useARIAStore.getState();
        expect(state.sessionId).toBeNull();
        expect(state.streamUrl).toBeNull();
        expect(state.taskStatus).toBe("idle");
        expect(state.taskDescription).toBe("");
        expect(state.uid).toBeNull();
        expect(state.idToken).toBeNull();
        expect(state.isSessionStarting).toBe(false);
    });

    it("has correct initial voice slice", () => {
        const state = useARIAStore.getState();
        expect(state.voiceStatus).toBe("idle");
        expect(state.isVoiceConnecting).toBe(false);
    });

    it("has correct initial thinking panel slice", () => {
        const state = useARIAStore.getState();
        expect(state.steps).toEqual([]);
        expect(state.panelStatus).toBe("idle");
        expect(state.taskSummary).toBe("");
        expect(state.errorMessage).toBeNull();
        expect(state.connectionStatus).toBe("disconnected");
    });

    // ── setState (session slice) ─────────────────────────────────────────

    it("sets sessionId and streamUrl", () => {
        useARIAStore.setState({
            sessionId: "sess_abc",
            streamUrl: "/api/stream/sess_abc",
        });
        const state = useARIAStore.getState();
        expect(state.sessionId).toBe("sess_abc");
        expect(state.streamUrl).toBe("/api/stream/sess_abc");
    });

    it("sets taskStatus to running", () => {
        useARIAStore.setState({ taskStatus: "running" });
        expect(useARIAStore.getState().taskStatus).toBe("running");
    });

    it("sets uid and idToken from Firebase auth", () => {
        useARIAStore.setState({ uid: "test-uid", idToken: "jwt-token" });
        const state = useARIAStore.getState();
        expect(state.uid).toBe("test-uid");
        expect(state.idToken).toBe("jwt-token");
    });

    it("sets isSessionStarting flag", () => {
        useARIAStore.setState({ isSessionStarting: true });
        expect(useARIAStore.getState().isSessionStarting).toBe(true);
    });

    // ── setState (thinking panel slice) ──────────────────────────────────

    it("sets steps array with PlanStep objects", () => {
        const steps = [
            {
                step_index: 0,
                description: "Navigate to Google",
                action: "navigate" as const,
                target: "https://google.com",
                value: null,
                confidence: 0.95,
                is_destructive: false,
                requires_user_input: false,
                user_input_reason: null,
                status: "pending" as const,
            },
        ];
        useARIAStore.setState({ steps });
        expect(useARIAStore.getState().steps).toHaveLength(1);
        expect(useARIAStore.getState().steps[0].description).toBe("Navigate to Google");
    });

    it("sets panelStatus and taskSummary", () => {
        useARIAStore.setState({
            panelStatus: "plan_ready",
            taskSummary: "Book a flight to Paris",
        });
        const state = useARIAStore.getState();
        expect(state.panelStatus).toBe("plan_ready");
        expect(state.taskSummary).toBe("Book a flight to Paris");
    });

    it("sets connectionStatus", () => {
        useARIAStore.setState({ connectionStatus: "connected" });
        expect(useARIAStore.getState().connectionStatus).toBe("connected");
    });

    it("sets errorMessage", () => {
        useARIAStore.setState({ errorMessage: "Something failed" });
        expect(useARIAStore.getState().errorMessage).toBe("Something failed");
    });

    // ── Immer integration ────────────────────────────────────────────────

    it("supports immer-style mutations via setState callback", () => {
        useARIAStore.setState({
            steps: [
                {
                    step_index: 0,
                    description: "Step A",
                    action: "click" as const,
                    target: null,
                    value: null,
                    confidence: 0.8,
                    is_destructive: false,
                    requires_user_input: false,
                    user_input_reason: null,
                    status: "pending" as const,
                },
            ],
        });

        useARIAStore.setState((state) => {
            const step = state.steps.find((s) => s.step_index === 0);
            if (step) step.status = "active";
        });

        expect(useARIAStore.getState().steps[0].status).toBe("active");
    });

    // ── resetAllSlices ───────────────────────────────────────────────────

    it("resetAllSlices returns all initial values", () => {
        const reset = resetAllSlices();
        expect(reset).toEqual(ARIA_INITIAL_STATE);
    });

    it("resetAllSlices restores store to defaults after mutations", () => {
        useARIAStore.setState({
            sessionId: "sess_dirty",
            taskStatus: "running",
            panelStatus: "executing",
            steps: [
                {
                    step_index: 0,
                    description: "X",
                    action: "click" as const,
                    target: null,
                    value: null,
                    confidence: 1,
                    is_destructive: false,
                    requires_user_input: false,
                    user_input_reason: null,
                    status: "active" as const,
                },
            ],
            connectionStatus: "connected",
            errorMessage: "fail",
        });

        useARIAStore.setState(resetAllSlices());

        const state = useARIAStore.getState();
        expect(state.sessionId).toBeNull();
        expect(state.taskStatus).toBe("idle");
        expect(state.panelStatus).toBe("idle");
        expect(state.steps).toEqual([]);
        expect(state.connectionStatus).toBe("disconnected");
        expect(state.errorMessage).toBeNull();
    });
});
