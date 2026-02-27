import React from "react";

type ConfidenceBadgeProps = {
  confidence: number;
};

export function ConfidenceBadge({ confidence }: ConfidenceBadgeProps) {
  let label = "Low";
  let bgClass = "bg-confidence-low";

  if (confidence >= 0.8) {
    label = "High";
    bgClass = "bg-confidence-high";
  } else if (confidence >= 0.5) {
    label = "Med";
    bgClass = "bg-confidence-mid";
  }

  return (
    <span
      className={`${bgClass} text-zinc-950 rounded-full px-2 py-0.5 text-xs font-medium shrink-0`}
    >
      {label}
    </span>
  );
}

export default ConfidenceBadge;
