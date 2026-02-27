import { render, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useARIAStore, resetAllSlices } from "@/lib/store/aria-store";

// Hoist mocks so they're available when vi.mock factories execute
const {
    mockGetIdToken,
    mockSignInAnonymously,
    mockUnsubscribe,
    mockOnAuthStateChanged,
    getAuthStateCallback,
    setAuthStateCallback,
} = vi.hoisted(() => {
    let _authStateCallback: ((user: unknown) => void) | null = null;
    return {
        mockGetIdToken: vi.fn().mockResolvedValue("mock-jwt-token"),
        mockSignInAnonymously: vi.fn().mockResolvedValue({ user: { uid: "anon-uid" } }),
        mockUnsubscribe: vi.fn(),
        mockOnAuthStateChanged: vi.fn((_auth: unknown, callback: (user: unknown) => void) => {
            _authStateCallback = callback;
            return vi.fn(); // unsubscribe
        }),
        getAuthStateCallback: () => _authStateCallback,
        setAuthStateCallback: (cb: ((user: unknown) => void) | null) => {
            _authStateCallback = cb;
        },
    };
});

vi.mock("firebase/auth", () => ({
    getAuth: vi.fn(() => ({})),
    signInAnonymously: (...args: unknown[]) => mockSignInAnonymously(...args),
    onAuthStateChanged: (...args: unknown[]) => mockOnAuthStateChanged(...args),
}));

vi.mock("@/lib/firebase", () => ({
    app: {},
    auth: {},
}));

import { FirebaseAuthProvider } from "./firebase-auth-provider";

describe("FirebaseAuthProvider", () => {
    beforeEach(() => {
        useARIAStore.setState(resetAllSlices());
        setAuthStateCallback(null);
        vi.clearAllMocks();
        // Re-set the mock implementation after clearAllMocks
        mockSignInAnonymously.mockResolvedValue({ user: { uid: "anon-uid" } });
        mockOnAuthStateChanged.mockImplementation((_auth: unknown, callback: (user: unknown) => void) => {
            setAuthStateCallback(callback);
            return mockUnsubscribe;
        });
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it("renders nothing (returns null)", () => {
        const { container } = render(<FirebaseAuthProvider />);
        expect(container.innerHTML).toBe("");
    });

    it("subscribes to auth state changes on mount", () => {
        render(<FirebaseAuthProvider />);
        expect(mockOnAuthStateChanged).toHaveBeenCalledTimes(1);
    });

    it("unsubscribes on unmount", () => {
        const { unmount } = render(<FirebaseAuthProvider />);
        unmount();
        expect(mockUnsubscribe).toHaveBeenCalledTimes(1);
    });

    it("sets uid and idToken in store when user exists", async () => {
        render(<FirebaseAuthProvider />);

        // Simulate auth state change with existing user
        const mockUser = {
            uid: "existing-uid-123",
            getIdToken: vi.fn().mockResolvedValue("jwt-token-abc"),
        };
        getAuthStateCallback()?.(mockUser);

        await waitFor(() => {
            const state = useARIAStore.getState();
            expect(state.uid).toBe("existing-uid-123");
            expect(state.idToken).toBe("jwt-token-abc");
        });
    });

    it("calls signInAnonymously when no user exists", async () => {
        render(<FirebaseAuthProvider />);

        // Simulate auth state change with null user (not signed in)
        getAuthStateCallback()?.(null);

        await waitFor(() => {
            expect(mockSignInAnonymously).toHaveBeenCalledTimes(1);
        });
    });

    it("does not set store values when signInAnonymously is called (waits for next auth callback)", () => {
        render(<FirebaseAuthProvider />);

        // Trigger null user — should call signInAnonymously but not set store directly
        getAuthStateCallback()?.(null);

        // Store should still be in initial state (signInAnonymously triggers
        // another onAuthStateChanged callback with the new user)
        const state = useARIAStore.getState();
        expect(state.uid).toBeNull();
        expect(state.idToken).toBeNull();
    });
});
