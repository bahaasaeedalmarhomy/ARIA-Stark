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
  it('pending: renders gray dot and bg-surface', () => {
    render(<StepItem step={mockStep({ status: "pending" })} />);
    expect(screen.getByText("●")).toHaveClass("text-zinc-500");
    const card = screen.getByTestId("step-card");
    expect(card.className).toMatch(/bg-surface/);
  });

  it('active: renders animate-pulse, bg-surface-raised, border-l-step-active', () => {
    render(<StepItem step={mockStep({ status: "active" })} />);
    const pulse = document.querySelector(".animate-pulse");
    expect(pulse).not.toBeNull();
    const card = screen.getByTestId("step-card");
    expect(card.className).toMatch(/bg-surface-raised/);
    expect(card.className).toMatch(/border-l-step-active/);
  });

  it('complete: renders checkmark ✓', () => {
    render(<StepItem step={mockStep({ status: "complete" })} />);
    expect(screen.getByText("✓")).toBeTruthy();
  });

  it('error: renders ✗', () => {
    render(<StepItem step={mockStep({ status: "error" })} />);
    expect(screen.getByText("✗")).toBeTruthy();
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
