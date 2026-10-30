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
  calendar: "M4 6h16v14H4zM4 10h16M8 3v4M16 3v4",
  bell: "M6 16V11a6 6 0 0112 0v5l2 2H4zM10 20a2 2 0 004 0",
  people: "M9 11a4 4 0 100-8 4 4 0 000 8zM2 21v-1a6 6 0 0112 0v1M17 11l2 2 4-4",
  inbox: "M4 13l2-8h12l2 8M4 13v6h16v-6M4 13h5l1 2h4l1-2h5",
  board: "M4 4h16v16H4zM9 4v16M15 4v16",
  wrench: "M14 6a4 4 0 015 5l-9 9-3-3 9-9a4 4 0 01-2-2zM5 19l-1 1",
  file: "M6 3h8l4 4v14H6zM14 3v4h4M9 13h6M9 17h6",
  gear: "M12 15a3 3 0 100-6 3 3 0 000 6zM19 12l2-1-1-3-2 .5-1.5-1.5.5-2-3-1-1 2h-2l-1-2-3 1 .5 2L6 7.5 4 7 3 10l2 1v2l-2 1 1 3 2-.5L7.5 18 7 20l3 1 1-2h2l1 2 3-1-.5-2 1.5-1.5 2 .5 1-3-2-1z",
  upload: "M12 16V4M7 9l5-5 5 5M4 20h16",
  download: "M12 4v12M7 11l5 5 5-5M4 20h16",
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
