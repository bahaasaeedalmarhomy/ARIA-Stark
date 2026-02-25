"use client";

import { TaskConfirmedBanner } from "@/components/session/TaskConfirmedBanner";
import { TaskInput } from "@/components/session/TaskInput";

export default function Home() {
  return (
    <main className="flex h-screen w-full min-w-0 bg-zinc-950 overflow-hidden">
      {/* Left: Browser Panel + Task Input */}
      <section className="flex-1 flex flex-col bg-zinc-950">
        <div className="flex-1 flex items-center justify-center text-zinc-500 text-sm">
          <p className="font-mono">Browser panel</p>
        </div>

        <div className="border-t border-zinc-800 flex flex-col gap-2 pb-2">
          <TaskConfirmedBanner />
          <TaskInput />
        </div>
      </section>

      {/* Right: Thinking Panel — fixed 400px */}
      <aside className="w-[400px] shrink-0 border-l border-zinc-800 flex flex-col bg-surface">
        {/* Placeholder — ThinkingPanel goes here in Story 2.4 */}
        <p className="p-4 text-zinc-500 text-sm font-mono">Thinking panel</p>
      </aside>
    </main>
  );
}
