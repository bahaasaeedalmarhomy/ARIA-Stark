import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ConfidenceBadge } from "./ConfidenceBadge";

describe("ConfidenceBadge", () => {
  it("renders High for confidence >= 0.8", () => {
    render(<ConfidenceBadge confidence={0.9} />);
    const badge = screen.getByText("High");
    expect(badge).toBeTruthy();
    expect(badge.className).toMatch(/bg-confidence-high/);
  });

  it("renders Med for 0.5 <= confidence < 0.8", () => {
    render(<ConfidenceBadge confidence={0.65} />);
    const badge = screen.getByText("Med");
    expect(badge).toBeTruthy();
    expect(badge.className).toMatch(/bg-confidence-mid/);
  });

  it("renders Low for confidence < 0.5", () => {
    render(<ConfidenceBadge confidence={0.3} />);
    const badge = screen.getByText("Low");
    expect(badge).toBeTruthy();
    expect(badge.className).toMatch(/bg-confidence-low/);
  });

  it("boundary: 0.8 → High", () => {
    render(<ConfidenceBadge confidence={0.8} />);
    const badge = screen.getByText("High");
    expect(badge).toBeTruthy();
  });

  it("boundary: 0.5 → Med", () => {
    render(<ConfidenceBadge confidence={0.5} />);
    const badge = screen.getByText("Med");
    expect(badge).toBeTruthy();
  });
}
)
