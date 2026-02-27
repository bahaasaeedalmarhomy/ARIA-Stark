"use client";

import React, { useEffect, useRef } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { StepItem } from "./StepItem";
import { useARIAStore } from "@/lib/store/aria-store";

export function ThinkingPanel() {
  const steps = useARIAStore((state) => state.steps);
  const panelStatus = useARIAStore((state) => state.panelStatus);
  const viewportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const activeStep = steps.find((s) => s.status === "active");
    if (!activeStep) return;
    const el = viewportRef.current?.querySelector(
      `[data-step-index="${activeStep.step_index}"]`
    );
    if (el && typeof (el as HTMLElement).scrollIntoView === "function") {
      (el as HTMLElement).scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [steps]);

  const headerBase =
    "px-4 py-3 border-b border-border-aria text-sm font-medium text-text-secondary flex items-center gap-2";
  const headerClass =
    panelStatus === "complete"
      ? `${headerBase} text-confidence-high`
      : panelStatus === "failed"
      ? `${headerBase} text-confidence-low`
      : headerBase;

  const headerLabel =
    panelStatus === "complete"
      ? "Done"
      : panelStatus === "failed"
      ? "Failed"
      : "Thinking";

  return (
    <div className="h-full w-full bg-surface flex flex-col">
      <div className={headerClass}>
        <span>{headerLabel}</span>
        {panelStatus === "planning" && (
          <span className="animate-pulse text-text-secondary">●</span>
        )}
      </div>

      <div ref={viewportRef} className="flex-1">
        <ScrollArea className="flex-1 px-4 py-3">
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
            <ul className="flex flex-col gap-2" role="list">
              {steps.map((step) => (
                <li key={step.step_index}>
                  <StepItem step={step} />
                </li>
              ))}
            </ul>
          )}
        </ScrollArea>
      </div>
    </div>
  );
}

export default ThinkingPanel;
