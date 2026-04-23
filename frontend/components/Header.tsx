"use client";

export function Header() {
  return (
    <header className="h-16 w-full bg-[#0066CC] text-white">
      <div className="mx-auto flex h-full w-full max-w-5xl items-center justify-between px-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/15 text-sm font-bold">
            PS
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold">PartSelect Agent</div>
            <div className="text-xs text-white/80">Refrigerator & Dishwasher Parts</div>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs text-white/90">
          <span className="relative inline-flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-300 opacity-60" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-300" />
          </span>
          Online
        </div>
      </div>
    </header>
  );
}

