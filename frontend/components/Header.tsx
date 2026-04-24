"use client";

export function Header() {
  return (
    <header className="w-full text-white">
      <div className="h-16 w-full bg-[#0b6a6a]">
        <div className="mx-auto flex h-full w-full max-w-5xl items-center justify-between px-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/15 text-sm font-bold">
            PA
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
      </div>
      <div className="w-full bg-[#f3c64e]">
        <div className="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-center gap-x-6 gap-y-2 px-4 py-2 text-[11px] font-medium text-[#1f2937]">
          <span>Price Match Guarantee</span>
          <span>Fast Shipping</span>
          <span>Genuine OEM Parts</span>
          <span>1 Year Warranty</span>
        </div>
      </div>
    </header>
  );
}

