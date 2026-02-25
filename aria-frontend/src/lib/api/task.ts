import type { StartTaskResponse } from "@/types/aria";

/**
 * Calls POST /api/task/start on the ARIA backend.
 *
 * @param taskDescription - Natural language task for ARIA to execute.
 * @param idToken - Firebase Anonymous Auth JWT, placed in Authorization header.
 * @returns Full canonical response envelope { success, data, error }.
 */
export async function startTask(
    taskDescription: string,
    idToken: string
): Promise<StartTaskResponse> {
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8080";

    try {
        const response = await fetch(`${backendUrl}/api/task/start`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${idToken}`,
            },
            body: JSON.stringify({ task_description: taskDescription }),
        });

        const data: StartTaskResponse = await response.json();
        return data;
    } catch (error) {
        // Network failure, CORS block, or non-JSON response
        const message =
            error instanceof Error ? error.message : "Unknown network error";
        return {
            success: false,
            data: null,
            error: { code: "NETWORK_ERROR", message },
        };
    }
}
