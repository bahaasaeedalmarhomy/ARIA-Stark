import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { StepItem } from "./StepItem";
import type { PlanStep } from "@/types/aria";

const mockStep = (overrides: Partial<PlanStep> = {}): PlanStep => ({
  step_index: 0,
  description: "Do something important",
  action: "click",
  target: null,
  value: null,
  confidence: 0.75,
  is_destructive: false,
  requires_user_input: false,
  user_input_reason: null,
  status: "pending",
  ...overrides,
});

describe("StepItem", () => {
  it('pending: renders circle icon', () => {
    const { container } = render(<StepItem step={mockStep({ status: "pending" })} />);
    const icon = container.querySelector('.lucide-circle');
    expect(icon).toBeTruthy();
    expect(icon).toHaveClass("text-text-disabled");
    const card = screen.getByTestId("step-card");
    expect(card.className).toMatch(/bg-surface/);
  });

  it('active: renders loader, bg-surface-raised, border-l-step-active', () => {
    const { container } = render(<StepItem step={mockStep({ status: "active" })} />);
    // Loader2 has animate-spin class
    const loader = container.querySelector('.animate-spin');
    expect(loader).toBeTruthy();
    const card = screen.getByTestId("step-card");
    expect(card.className).toMatch(/bg-surface-raised/);
    expect(card.className).toMatch(/border-l-step-active/);
  });

  it('complete: renders check icon', () => {
    const { container } = render(<StepItem step={mockStep({ status: "complete" })} />);
    const icon = container.querySelector('.lucide-check');
    expect(icon).toBeTruthy();
    expect(icon).toHaveClass("text-confidence-high");
  });

  it('error: renders x icon', () => {
    const { container } = render(<StepItem step={mockStep({ status: "error" })} />);
    const icon = container.querySelector('.lucide-x');
    expect(icon).toBeTruthy();
    expect(icon).toHaveClass("text-confidence-low");
  });

  it('renders description in font-mono', () => {
    render(<StepItem step={mockStep({ description: "Mono text" })} />);
    expect(screen.getByText("Mono text")).toHaveClass("font-mono");
  });

  it('renders ConfidenceBadge with confidence text', () => {
    render(<StepItem step={mockStep({ confidence: 0.9 })} />);
    expect(screen.getByText("High")).toBeTruthy();
  });
});
