"use client";

import { useARIAStore } from "@/lib/store/aria-store";

export function TaskConfirmedBanner() {
    const { sessionId, taskDescription } = useARIAStore();

    if (!sessionId) return null;

    return (
        <div
            id="task-confirmed-banner"
            className="mx-4 p-3 rounded-md bg-zinc-800 border border-emerald-800"
        >
            <p className="text-xs text-zinc-400">Task received:</p>
            <p className="text-sm text-emerald-400 font-mono mt-1">
                {taskDescription}
            </p>
        </div>
    );
}

