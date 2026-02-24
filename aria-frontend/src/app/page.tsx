export default function Home() {
  return (
    <main className="flex h-screen w-full min-w-0 bg-zinc-950 overflow-hidden">
      {/* Left: Browser Panel — flex-grow */}
      <section className="flex-1 flex flex-col items-center justify-center text-zinc-500 text-sm">
        {/* Placeholder — BrowserPanel goes here in Story 3.x */}
        <p className="font-mono">Browser panel</p>
      </section>

      {/* Right: Thinking Panel — fixed 400px */}
      <aside className="w-[400px] shrink-0 border-l border-zinc-800 flex flex-col bg-surface">
        {/* Placeholder — ThinkingPanel goes here in Story 2.4 */}
        <p className="p-4 text-zinc-500 text-sm font-mono">Thinking panel</p>
      </aside>
    </main>
  );
}

