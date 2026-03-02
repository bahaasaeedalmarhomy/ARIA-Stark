"use client";

import React, { useState } from "react";
import { useARIAStore } from "@/lib/store/aria-store";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8080";

interface InputRequestBannerProps {
  message: string;
  sessionId: string;
  onSubmitted?: () => void;
}

export function InputRequestBanner({
  message,
  sessionId,
  onSubmitted,
}: InputRequestBannerProps) {
  const [userInput, setUserInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);

  const handleSend = async () => {
    const trimmed = userInput.trim();
    if (!trimmed) return;

    setIsLoading(true);
    setErrorText(null);

    try {
      const res = await fetch(
        `${BACKEND_URL}/api/task/${sessionId}/input`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ value: trimmed }),
        }
      );

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const msg =
          body?.error?.message ?? `Request failed with status ${res.status}`;
        setErrorText(msg);
        return;
      }

      setUserInput("");
      useARIAStore.setState({
        taskStatus: "running",
        awaitingInputMessage: null,
      });
      onSubmitted?.();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Network error — please retry";
      setErrorText(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Ctrl+Enter / Cmd+Enter submits
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div
      data-testid="input-request-banner"
      className="mt-3 p-3 rounded-md border border-amber-500/40 bg-amber-950/20"
    >
      <div className="flex items-start gap-2 mb-2">
        <span className="text-amber-400 mt-0.5" aria-hidden="true">
          ⚠
        </span>
        <p className="text-sm text-amber-300 leading-relaxed">{message}</p>
      </div>

      <textarea
        className="w-full resize-none rounded-sm bg-surface-2 border border-border-aria px-2 py-1.5 text-sm
          font-mono text-text-primary placeholder:text-text-disabled focus:outline-none
          focus:ring-1 focus:ring-amber-500/50 min-h-[60px]"
        placeholder="Type your response…"
        value={userInput}
        onChange={(e) => setUserInput(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={isLoading}
        rows={2}
      />

      {errorText && (
        <p className="mt-1 text-xs text-rose-400">{errorText}</p>
      )}

      <div className="mt-2 flex justify-end">
        <button
          type="button"
          onClick={handleSend}
          disabled={isLoading || !userInput.trim()}
          className="flex items-center gap-1.5 rounded-sm bg-amber-600 px-3 py-1.5 text-xs font-medium
            text-white hover:bg-amber-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? (
            <>
              <span
                className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent"
                aria-hidden="true"
              />
              Sending…
            </>
          ) : (
            "Send"
          )}
        </button>
      </div>
    </div>
  );
}

export default InputRequestBanner;
