import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { InputRequestBanner } from "./InputRequestBanner";
import { useARIAStore, resetAllSlices } from "@/lib/store/aria-store";

describe("InputRequestBanner", () => {
  beforeEach(() => {
    useARIAStore.setState(resetAllSlices());
    vi.clearAllMocks();
  });

  it("renders with the provided message text", () => {
    render(
      <InputRequestBanner
        message="CAPTCHA encountered — manual intervention required"
        sessionId="sess_abc123"
      />
    );

    expect(
      screen.getByText("CAPTCHA encountered — manual intervention required")
    ).toBeTruthy();
  });

  it("has data-testid='input-request-banner' on wrapper div", () => {
    render(
      <InputRequestBanner message="Please solve the CAPTCHA" sessionId="sess_abc123" />
    );

    expect(screen.getByTestId("input-request-banner")).toBeTruthy();
  });

  it("renders a textarea for user input", () => {
    render(
      <InputRequestBanner message="Need your input" sessionId="sess_abc123" />
    );

    const textarea = screen.getByPlaceholderText("Type your response…");
    expect(textarea).toBeTruthy();
  });

  it("renders a Send button", () => {
    render(
      <InputRequestBanner message="Need your input" sessionId="sess_abc123" />
    );

    expect(screen.getByRole("button", { name: /send/i })).toBeTruthy();
  });

  it("Send button is disabled when textarea is empty", () => {
    render(
      <InputRequestBanner message="Need your input" sessionId="sess_abc123" />
    );

    const button = screen.getByRole("button", { name: /send/i }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
  });

  it("Send button becomes enabled when user types text", async () => {
    render(
      <InputRequestBanner message="Need your input" sessionId="sess_abc123" />
    );

    const textarea = screen.getByPlaceholderText("Type your response…");
    fireEvent.change(textarea, { target: { value: "user text" } });

    const button = screen.getByRole("button", { name: /send/i }) as HTMLButtonElement;
    expect(button.disabled).toBe(false);
  });

  it("calls POST /api/task/{sessionId}/input with user input on Send click", async () => {
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, data: { queued: true }, error: null }),
    } as Response);

    render(
      <InputRequestBanner message="Need your input" sessionId="sess_test" />
    );

    const textarea = screen.getByPlaceholderText("Type your response…");
    fireEvent.change(textarea, { target: { value: "my answer" } });

    const button = screen.getByRole("button", { name: /send/i });
    fireEvent.click(button);

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining("/api/task/sess_test/input"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ value: "my answer" }),
        })
      );
    });
  });

  it("shows loading state while fetch is in-flight", async () => {
    // Use a promise we can control to simulate a slow fetch
    let resolveFetch!: (value: Response) => void;
    const pendingFetch = new Promise<Response>((resolve) => {
      resolveFetch = resolve;
    });
    vi.spyOn(global, "fetch").mockReturnValue(pendingFetch);

    render(
      <InputRequestBanner message="Need your input" sessionId="sess_load" />
    );

    const textarea = screen.getByPlaceholderText("Type your response…");
    fireEvent.change(textarea, { target: { value: "some input" } });

    const button = screen.getByRole("button", { name: /send/i });
    fireEvent.click(button);

    // Button should now show loading indicator text (or be disabled)
    await waitFor(() => {
      const btn = screen.getByRole("button") as HTMLButtonElement;
      // Either the button shows "Sending…" text or is disabled during loading
      const isSendingOrDisabled =
        btn.textContent?.includes("Sending") || btn.disabled;
      expect(isSendingOrDisabled).toBe(true);
    });

    // Resolve the fetch
    resolveFetch({
      ok: true,
      json: async () => ({ success: true }),
    } as Response);
  });

  it("calls onSubmitted after successful POST", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, data: { queued: true }, error: null }),
    } as Response);

    const onSubmitted = vi.fn();

    render(
      <InputRequestBanner
        message="Need your input"
        sessionId="sess_submitted"
        onSubmitted={onSubmitted}
      />
    );

    const textarea = screen.getByPlaceholderText("Type your response…");
    fireEvent.change(textarea, { target: { value: "submitted" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => {
      expect(onSubmitted).toHaveBeenCalledTimes(1);
    });
  });

  it("shows error text below textarea on fetch failure", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({
        error: { message: "Session not found" },
      }),
    } as Response);

    render(
      <InputRequestBanner message="Need your input" sessionId="sess_fail" />
    );

    const textarea = screen.getByPlaceholderText("Type your response…");
    fireEvent.change(textarea, { target: { value: "test" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => {
      expect(screen.getByText("Session not found")).toBeTruthy();
    });
  });

  it("shows generic error text when fetch throws a network error", async () => {
    vi.spyOn(global, "fetch").mockRejectedValue(new Error("Failed to fetch"));

    render(
      <InputRequestBanner message="Need your input" sessionId="sess_neterr" />
    );

    const textarea = screen.getByPlaceholderText("Type your response…");
    fireEvent.change(textarea, { target: { value: "test" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => {
      expect(screen.getByText("Failed to fetch")).toBeTruthy();
    });
  });
});
