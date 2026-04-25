"use client";

export function Header() {
  return (
    <header className="w-full shrink-0 text-white">
      <div className="h-[52px] w-full bg-[#0b6a6a]">
        <div className="mx-auto flex h-full w-full max-w-5xl items-center justify-between gap-3 px-4">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/15 text-sm font-bold">
              PS
            </div>
            <div className="min-w-0 leading-tight">
              <div className="truncate text-sm font-semibold sm:text-[15px]">
                PartSelect Assistant
              </div>
              <div className="truncate text-[11px] text-white/85 sm:text-xs">
                Refrigerator &amp; dishwasher parts
              </div>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-3">
            <a
              href="https://www.partselect.com"
              target="_blank"
              rel="noreferrer"
              className="hidden rounded-lg border border-white/25 bg-white/10 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-white/20 sm:inline-block"
            >
              Shop PartSelect
            </a>
            <div className="flex items-center gap-1.5 text-[11px] text-white/90 sm:text-xs">
              <span className="relative inline-flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-300 opacity-50" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-300" />
              </span>
              <span className="hidden sm:inline">Online</span>
            </div>
          </div>
        </div>
      </div>
      <div className="w-full bg-[#f3c64e]">
        <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-center gap-x-5 gap-y-1.5 px-3 py-2 text-[10px] font-semibold uppercase tracking-wide text-zinc-900 sm:gap-x-8 sm:text-[11px]">
          <span>Price match</span>
          <span>Fast shipping</span>
          <span>OEM parts</span>
          <span>1-year warranty</span>
        </div>
      </div>
    </header>
  );
}
