import React from "react";
import type { PlanStep } from "@/types/aria";
import { ConfidenceBadge } from "./ConfidenceBadge";

type StepItemProps = {
  step: PlanStep;
};

export function StepItem({ step }: StepItemProps) {
  const isActive = step.status === "active";

  const cardClasses =
    "rounded-md border border-border-aria px-3 py-2 flex items-start gap-2 transition-colors " +
    (isActive
      ? "bg-surface-raised border-l-2 border-l-step-active"
      : "bg-surface");

  const descriptionClasses =
    "font-mono " +
    (isActive ? "text-text-primary" : "text-text-secondary");

  let statusIcon: React.ReactNode = null;
  switch (step.status) {
    case "pending":
      statusIcon = <span className="text-zinc-500">●</span>;
      break;
    case "active":
      statusIcon = <span className="animate-pulse text-step-active">●</span>;
      break;
    case "complete":
      statusIcon = <span className="text-confidence-high">✓</span>;
      break;
    case "error":
      statusIcon = <span className="text-confidence-low">✗</span>;
      break;
  }

  return (
    <div
      data-testid="step-card"
      data-step-index={step.step_index}
      className={cardClasses}
    >
      <div className="shrink-0 mt-0.5 text-xs text-text-secondary">
        {step.step_index + 1}
      </div>
      <div className="flex-1 min-w-0 flex items-center gap-2">
        <span className={descriptionClasses}>{step.description}</span>
        <span className="shrink-0">{statusIcon}</span>
        <ConfidenceBadge confidence={step.confidence} />
      </div>
    </div>
  );
}

export default StepItem;
