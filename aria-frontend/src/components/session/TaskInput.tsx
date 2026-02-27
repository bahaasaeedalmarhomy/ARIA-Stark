"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { startTask } from "@/lib/api/task";
import { useARIAStore, resetAllSlices } from "@/lib/store/aria-store";
import type { StepStatus } from "@/types/aria";

export function TaskInput() {
  const { idToken, taskStatus, isSessionStarting } = useARIAStore();

  const [taskDescription, setTaskDescription] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const submitTask = async () => {
    if (!idToken) return;

    setErrorMessage(null);
    useARIAStore.setState({ isSessionStarting: true });

    try {
      const response = await startTask(taskDescription, idToken);

      if (response.success && response.data) {
        // Reset store first, preserving auth
        useARIAStore.setState({
          ...resetAllSlices(),
          uid: useARIAStore.getState().uid,
          idToken: useARIAStore.getState().idToken,
        });

        // Hydrate from REST response if available
        if (response.data.step_plan) {
          const { steps, task_summary } = response.data.step_plan;
          useARIAStore.setState({
            steps: steps.map((s) => ({ ...s, status: "pending" as StepStatus })),
            taskSummary: task_summary,
            panelStatus: "plan_ready",
          });
        }

        useARIAStore.setState({
          sessionId: response.data.session_id,
          taskDescription,
          taskStatus: "running",
          isSessionStarting: false,
        });
        setTaskDescription("");
      } else {
        setErrorMessage(
          response.error?.message ?? "An unexpected error occurred"
        );
      }
    } catch {
      setErrorMessage("An unexpected error occurred. Please try again.");
    } finally {
      useARIAStore.setState({ isSessionStarting: false });
    }
  };

    const handleSubmit = async (event?: FormEvent) => {
        event?.preventDefault();

        if (!taskDescription.trim()) return;

        if (taskStatus !== "idle") {
            setConfirmOpen(true);
            return;
        }

        await submitTask();
    };

    const handleConfirmStartNew = async () => {
        setConfirmOpen(false);
        await submitTask();
    };

    return (
        <div className="flex flex-col gap-2 p-4">
            <form className="flex flex-col gap-2" onSubmit={handleSubmit}>
                <textarea
                    id="task-input"
                    aria-label="Task description"
                    aria-describedby={errorMessage ? "task-error" : undefined}
                    rows={3}
                    maxLength={10000}
                    placeholder="Describe a task for ARIA..."
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-md p-3 text-zinc-100 placeholder:text-zinc-500 resize-none focus:outline-none focus:ring-2 focus:ring-[var(--color-step-active)] text-sm"
                    value={taskDescription}
                    onChange={(e) => setTaskDescription(e.target.value)}
                    disabled={Boolean(isSessionStarting)}
                />

                {errorMessage && (
                    <p id="task-error" className="text-rose-400 text-xs">
                        {errorMessage}
                    </p>
                )}

                <Button
                    id="start-task-btn"
                    type="submit"
                    disabled={!idToken || Boolean(isSessionStarting)}
                >
                    {isSessionStarting ? (
                        <span className="flex items-center gap-2">
                            <span className="h-4 w-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                            Starting...
                        </span>
                    ) : (
                        "Start Task"
                    )}
                </Button>
            </form>

            <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Start a new task?</DialogTitle>
                        <DialogDescription>
                            Cancel current task and start a new one?
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => setConfirmOpen(false)}
                        >
                            Cancel
                        </Button>
                        <Button
                            type="button"
                            variant="destructive"
                            onClick={handleConfirmStartNew}
                            disabled={!idToken || Boolean(isSessionStarting)}
                        >
                            Confirm
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
