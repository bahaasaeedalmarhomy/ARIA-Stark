import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { startTask } from "./task";

// Store original fetch
const originalFetch = globalThis.fetch;

beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_BACKEND_URL", "http://localhost:8080");
});

afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    globalThis.fetch = originalFetch;
});

describe("startTask", () => {
    it("sends POST to /api/task/start with correct headers and body", async () => {
        const mockResponse = {
            success: true,
            data: { session_id: "sess_abc", stream_url: "/api/stream/sess_abc" },
            error: null,
        };

        globalThis.fetch = vi.fn().mockResolvedValue({
            json: () => Promise.resolve(mockResponse),
        });

        await startTask("Search for cats", "my-firebase-token");

        expect(globalThis.fetch).toHaveBeenCalledWith(
            "http://localhost:8080/api/task/start",
            expect.objectContaining({
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: "Bearer my-firebase-token",
                },
                body: JSON.stringify({ task_description: "Search for cats" }),
            })
        );
    });

    it("returns canonical success response on 200", async () => {
        const mockResponse = {
            success: true,
            data: {
                session_id: "sess_00000000-0000-0000-0000-000000000000",
                stream_url: "/api/stream/sess_00000000-0000-0000-0000-000000000000",
            },
            error: null,
        };

        globalThis.fetch = vi.fn().mockResolvedValue({
            json: () => Promise.resolve(mockResponse),
        });

        const result = await startTask("Book a flight", "token123");

        expect(result.success).toBe(true);
        expect(result.data?.session_id).toBe("sess_00000000-0000-0000-0000-000000000000");
        expect(result.data?.stream_url).toBe(
            "/api/stream/sess_00000000-0000-0000-0000-000000000000"
        );
        expect(result.error).toBeNull();
    });

    it("returns canonical error response on API error (e.g. 401)", async () => {
        const mockResponse = {
            success: false,
            data: null,
            error: { code: "UNAUTHORIZED", message: "Invalid token" },
        };

        globalThis.fetch = vi.fn().mockResolvedValue({
            json: () => Promise.resolve(mockResponse),
        });

        const result = await startTask("Do something", "bad-token");

        expect(result.success).toBe(false);
        expect(result.data).toBeNull();
        expect(result.error?.code).toBe("UNAUTHORIZED");
        expect(result.error?.message).toBe("Invalid token");
    });

    it("returns NETWORK_ERROR on fetch failure (e.g. CORS block)", async () => {
        globalThis.fetch = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));

        const result = await startTask("Do something", "token");

        expect(result.success).toBe(false);
        expect(result.data).toBeNull();
        expect(result.error?.code).toBe("NETWORK_ERROR");
        expect(result.error?.message).toBe("Failed to fetch");
    });

    it("returns NETWORK_ERROR with 'Unknown network error' for non-Error throws", async () => {
        globalThis.fetch = vi.fn().mockRejectedValue("string error");

        const result = await startTask("Do something", "token");

        expect(result.success).toBe(false);
        expect(result.error?.code).toBe("NETWORK_ERROR");
        expect(result.error?.message).toBe("Unknown network error");
    });

    it("uses default backend URL when NEXT_PUBLIC_BACKEND_URL is not set", async () => {
        vi.unstubAllEnvs();
        // process.env.NEXT_PUBLIC_BACKEND_URL is undefined → falls back to default

        const mockResponse = {
            success: true,
            data: { session_id: "sess_xyz", stream_url: "/api/stream/sess_xyz" },
            error: null,
        };

        globalThis.fetch = vi.fn().mockResolvedValue({
            json: () => Promise.resolve(mockResponse),
        });

        await startTask("Test task", "token");

        const calledUrl = (globalThis.fetch as ReturnType<typeof vi.fn>).mock
            .calls[0][0] as string;
        expect(calledUrl).toBe("http://localhost:8080/api/task/start");
    });
});
