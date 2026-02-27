import React from "react";
import type { PlanStep } from "@/types/aria";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { Check, X, Loader2, Circle } from "lucide-react";

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
    "font-mono text-sm " +
    (isActive ? "text-text-primary" : "text-text-secondary");

  let statusIcon: React.ReactNode = null;
  switch (step.status) {
    case "pending":
      statusIcon = <Circle className="w-4 h-4 text-text-disabled fill-current" />;
      break;
    case "active":
      statusIcon = <Loader2 className="w-4 h-4 animate-spin text-step-active" />;
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
      <div className="flex-1 min-w-0 flex items-center gap-2">
        <span className={descriptionClasses}>{step.description}</span>
        <span className="shrink-0 flex items-center justify-center w-5 h-5">
          {statusIcon}
        </span>
        <ConfidenceBadge confidence={step.confidence} />
      </div>
    </div>
  );
}

export default StepItem;
