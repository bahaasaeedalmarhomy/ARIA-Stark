import React from "react";
import type { PlanStep } from "@/types/aria";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { ScreenshotViewer } from "./ScreenshotViewer";
import { Check, X, Loader2, Circle } from "lucide-react";

type StepItemProps = {
  step: PlanStep;
};

export function StepItem({ step }: StepItemProps) {
  const isActive = step.status === "active";
  const isPaused = step.status === "paused";

  const cardClasses =
    "rounded-md border border-border-aria px-3 py-2 flex items-start gap-2 transition-colors " +
    (isActive
      ? "bg-surface-raised border-l-2 border-l-step-active"
      : isPaused
        ? "bg-zinc-800 border-l-2 border-l-violet-400"
        : "bg-surface");

  const descriptionClasses =
    "font-mono text-sm " +
    (isActive || isPaused ? "text-text-primary" : "text-text-secondary");

  let statusIcon: React.ReactNode = null;
  switch (step.status) {
    case "pending":
      statusIcon = <Circle className="w-4 h-4 text-text-disabled fill-current" />;
      break;
    case "active":
      statusIcon = <Loader2 className="w-4 h-4 animate-spin text-step-active" />;
      break;
    case "paused":
      statusIcon = <span className="text-violet-400 text-sm leading-none">⏸</span>;
      break;
    case "complete":
      statusIcon = <Check className="w-4 h-4 text-confidence-high" />;
      break;
    case "error":
      statusIcon = <X className="w-4 h-4 text-confidence-low" />;
      break;
  }

  return (
    <div
      data-testid="step-card"
      data-step-index={step.step_index}
      className={cardClasses}
      aria-current={isActive ? "step" : undefined}
    >
      <div className="shrink-0 mt-0.5 text-xs text-text-secondary font-mono">
        {step.step_index + 1}
      </div>
      <div className="flex-1 min-w-0 flex flex-col">
        <div className="flex items-center gap-2">
          <span className={descriptionClasses}>{step.description}</span>
          <span className="shrink-0 flex items-center justify-center w-5 h-5">
            {statusIcon}
          </span>
          <ConfidenceBadge confidence={step.confidence} />
        </div>
        {step.status === "paused" && (
          <span className="text-violet-400 text-xs font-medium mt-1 block">
            Paused — listening
          </span>
        )}
        {step.status === "complete" && step.screenshot_url && (
          <ScreenshotViewer
            screenshotUrl={step.screenshot_url}
            alt={`Screenshot for step ${step.step_index + 1}`}
          />
        )}
      </div>
    </div>
  );
}

export default StepItem;
