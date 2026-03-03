"use client";

import React, { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { StepItem } from "./StepItem";
import { InputRequestBanner } from "./InputRequestBanner";
import { useARIAStore } from "@/lib/store/aria-store";
import { useFirestoreSession } from "@/lib/hooks/useFirestoreSession";

export function ThinkingPanel() {
  const steps = useARIAStore((state) => state.steps);
  const panelStatus = useARIAStore((state) => state.panelStatus);
  const taskSummary = useARIAStore((state) => state.taskSummary);
  const taskStatus = useARIAStore((state) => state.taskStatus);
  const awaitingInputMessage = useARIAStore((state) => state.awaitingInputMessage);
  const sessionId = useARIAStore((state) => state.sessionId);
  const auditLog = useARIAStore((state) => state.auditLog);
  const viewportRef = useRef<HTMLDivElement>(null);
  const prevActiveIndexRef = useRef<number | null>(null);

  useFirestoreSession();

  useEffect(() => {
    const activeStep = steps.find((s) => s.status === "active");
    if (!activeStep) return;

    const activeIndex = activeStep.step_index;
    if (prevActiveIndexRef.current === activeIndex) return;
    prevActiveIndexRef.current = activeIndex;

    const el = viewportRef.current?.querySelector(
      `[data-step-index="${activeIndex}"]`
    );
    if (el) el.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [steps]);

  const headerBase =
    "px-4 py-3 border-b border-border-aria text-sm font-medium text-text-secondary flex items-center gap-2";
  const headerClass =
    panelStatus === "complete"
      ? `${headerBase} text-confidence-high`
      : panelStatus === "failed"
      ? `${headerBase} text-confidence-low`
      : panelStatus === "awaiting_input"
      ? `${headerBase} text-amber-400`
      : headerBase;

  const headerLabel =
    panelStatus === "complete"
      ? "Done"
      : panelStatus === "failed"
      ? "Failed"
      : panelStatus === "awaiting_input"
      ? "Awaiting Input"
      : "Thinking";

  return (
    <div className="h-full w-full bg-surface flex flex-col">
      <div className={headerClass} role="status" aria-live="polite">
        <span>{headerLabel}</span>
        {panelStatus === "planning" && (
          <span className="animate-pulse text-text-secondary">●</span>
        )}
      </div>

      <div ref={viewportRef} className="flex-1">
        <ScrollArea className="h-full px-4 py-3">
          {taskSummary && (
            <div id="task-summary" className="mb-3 pb-3 border-b border-border-aria">
              <p className="text-xs text-text-secondary leading-relaxed">
                <span className="font-medium text-text-primary">Task understood:</span>{" "}
                {taskSummary}
              </p>
            </div>
          )}
          {steps.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              {panelStatus === "planning" ? (
                <p className="animate-pulse text-text-secondary text-sm font-mono">
                  Planning…
                </p>
              ) : panelStatus === "idle" ? (
                <p className="text-text-disabled text-sm font-mono">
                  Waiting for task…
                </p>
              ) : null}
            </div>
          ) : (
            <ul
              className="flex flex-col gap-2"
              role="list"
              aria-label="Step plan"
              aria-describedby={taskSummary ? "task-summary" : undefined}
            >
              {steps.map((step) => (
                <li
                  key={step.step_index}
                  className="animate-step-enter"
                  style={{ animationDelay: `${step.step_index * 60}ms` }}
                >
                  <StepItem step={step} />
                </li>
              ))}
            </ul>
          )}          {panelStatus === "complete" && auditLog.length > 0 && (
            <div className="mt-4 pt-3 border-t border-border-aria" data-testid="audit-log-section">
              <p className="text-xs text-text-secondary mb-2 font-medium">
                Audit Log — {auditLog.length} step{auditLog.length !== 1 ? "s" : ""} recorded
              </p>
              <ul className="flex flex-col gap-1" role="list" aria-label="Audit log">
                {auditLog.map((entry) => (
                  <li
                    key={entry.step_index}
                    className="text-xs font-mono text-text-secondary flex items-start gap-2"
                  >
                    <span className="text-text-primary shrink-0">
                      #{entry.step_index + 1}
                    </span>
                    <span className="flex-1">{entry.description}</span>
                    {entry.screenshot_url && (
                      <span className="text-blue-400 shrink-0">[screenshot]</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}          {taskStatus === "awaiting_input" && awaitingInputMessage && sessionId && (
            <InputRequestBanner
              message={awaitingInputMessage}
              sessionId={sessionId}
              onSubmitted={() =>
                useARIAStore.setState({
                  taskStatus: "running",
                  awaitingInputMessage: null,
                })
              }
            />
          )}        </ScrollArea>
      </div>
    </div>
  );
}
