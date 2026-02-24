export function ViewportWarning() {
  return (
    <div aria-hidden="true" className="xl:hidden fixed inset-0 z-50 flex items-center justify-center bg-zinc-950 p-8 text-center">
      <div className="max-w-sm space-y-3">
        <p className="text-zinc-200 text-lg font-semibold">Screen too small</p>
        <p className="text-zinc-400 text-sm">
          ARIA requires a minimum viewport of 1280px wide. Please use a desktop browser.
        </p>
      </div>
    </div>
  );
}
