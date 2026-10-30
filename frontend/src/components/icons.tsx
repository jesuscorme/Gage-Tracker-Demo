// Minimal stroke icon set (24px grid, currentColor).

const P = {
  dashboard: "M3 13h8V3H3zM13 21h8V11h-8zM3 21h8v-6H3zM13 3v6h8V3z",
  gauge: "M12 14l4-4M3.5 17a9 9 0 1117 0M7 17h10",
  calibration: "M4 20h16M6 20V9l6-5 6 5v11M10 20v-5h4v5",
  msa: "M4 19V5M4 19h16M8 15l3-4 3 2 4-6",
  lab: "M9 3h6M10 3v6l-5 9a2 2 0 002 3h10a2 2 0 002-3l-5-9V3",
  standards: "M4 8h16v8H4zM8 8v3M12 8v4M16 8v3",
  oot: "M12 3l9 16H3zM12 10v4M12 17h.01",
  types: "M4 6h16M4 12h10M4 18h7",
  org: "M3 21h18M5 21V8l7-5 7 5v13M9 21v-6h6v6",
  users: "M16 19v-1a4 4 0 00-4-4H7a4 4 0 00-4 4v1M9.5 10a3.5 3.5 0 100-7 3.5 3.5 0 000 7zM21 19v-1a4 4 0 00-3-3.9M15.5 3.1a3.5 3.5 0 010 6.8",
  audit: "M9 4h6l1 2h3v15H5V6h3zM9 12l2 2 4-4",
  menu: "M4 6h16M4 12h16M4 18h16",
  close: "M6 6l12 12M18 6L6 18",
  plus: "M12 5v14M5 12h14",
  logout: "M15 4h4v16h-4M10 8l-4 4 4 4M6 12h11",
  back: "M15 6l-6 6 6 6",
  lock: "M6 11h12v9H6zM8 11V8a4 4 0 018 0v3",
} as const;

export type IconName = keyof typeof P;

export function Icon({ name, size = 18, className }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      className={className}
    >
      <path d={P[name]} />
    </svg>
  );
}
