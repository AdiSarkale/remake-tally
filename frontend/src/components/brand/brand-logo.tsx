export function BrandMark({ className = "size-8" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 64 64" role="img" aria-label="Nexora ERP">
      <defs>
        <linearGradient id="nexora-ring" x1="8%" y1="10%" x2="92%" y2="90%">
          <stop offset="0%" stopColor="#FFB21A" />
          <stop offset="48%" stopColor="#F59E0B" />
          <stop offset="100%" stopColor="#C77700" />
        </linearGradient>
      </defs>
      <path fill="url(#nexora-ring)" fillRule="evenodd" d="M32 3a29 29 0 1 0 0 58 29 29 0 0 0 0-58Zm0 15a14 14 0 1 1 0 28 14 14 0 0 1 0-28Z" />
      <path d="M12 15 24 27 13 43 5 33Z" fill="#FFB21A" opacity=".75" />
      <path d="M41 8 55 18 44 29 33 17Z" fill="#E88700" opacity=".8" />
      <path d="M47 39 59 31 55 48 42 55Z" fill="#C77700" opacity=".65" />
    </svg>
  );
}

export function BrandLockup({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <BrandMark className={compact ? "size-7 shrink-0" : "size-10 shrink-0"} />
      <div className="leading-none">
        <div className="text-sm font-bold tracking-[0.12em] text-foreground">NEXORA</div>
        <div className="mt-1 flex items-center gap-1.5">
          <span className="h-px w-3 bg-[#F59E0B]" />
          <span className="text-[10px] font-semibold tracking-[0.38em] text-foreground">ERP</span>
          <span className="h-px w-3 bg-[#F59E0B]" />
        </div>
      </div>
    </div>
  );
}
