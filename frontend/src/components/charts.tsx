// Small dependency-free SVG charts for statistical results (light/dark via currentColor tokens).

const PALETTE = ["#1f5c99", "#d66e1e", "#2c8c50", "#963ca0", "#7a7a7a"];

export interface Series { label: string; values: (number | null)[]; points?: boolean }
export interface HLine { value: number | null | undefined; label: string; tone?: "limit" | "center" | "ref" }

function bounds(values: number[]): [number, number] {
  let lo = Math.min(...values);
  let hi = Math.max(...values);
  if (lo === hi) {
    lo -= 1;
    hi += 1;
  }
  const pad = (hi - lo) * 0.08;
  return [lo - pad, hi + pad];
}

const fmt = (v: number) => (Math.abs(v) >= 100 ? v.toFixed(1) : Math.abs(v) >= 1 ? v.toFixed(3) : v.toPrecision(3));

export function LineChart({ title, series, hlines = [], height = 200, xLabels }: {
  title: string; series: Series[]; hlines?: HLine[]; height?: number; xLabels?: (string | number)[];
}) {
  const all = series.flatMap((s) => s.values.filter((v): v is number => v !== null && Number.isFinite(v)))
    .concat(hlines.map((h) => h.value).filter((v): v is number => typeof v === "number"));
  if (!all.length) return null;
  const [lo, hi] = bounds(all);
  const W = 640;
  const H = height;
  const L = 48;
  const R = 70;
  const T = 10;
  const B = 22;
  const n = Math.max(...series.map((s) => s.values.length));
  const x = (i: number) => L + ((W - L - R) * (i + 0.5)) / n;
  const y = (v: number) => T + (H - T - B) * (1 - (v - lo) / (hi - lo));
  return (
    <figure className="w-full">
      <figcaption className="mb-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-3">{title}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full text-ink-3" role="img" aria-label={title}>
        <rect x={L} y={T} width={W - L - R} height={H - T - B} fill="none" stroke="currentColor" strokeOpacity={0.3} />
        <text x={L - 4} y={T + 8} textAnchor="end" fontSize={10} fill="currentColor">{fmt(hi)}</text>
        <text x={L - 4} y={H - B} textAnchor="end" fontSize={10} fill="currentColor">{fmt(lo)}</text>
        {hlines.map((h, i) => typeof h.value === "number" && (
          <g key={i}>
            <line x1={L} x2={W - R} y1={y(h.value)} y2={y(h.value)} strokeDasharray="4 3"
              stroke={h.tone === "limit" ? "#c0392b" : h.tone === "ref" ? "#2c8c50" : "currentColor"} />
            <text x={W - R + 4} y={y(h.value) + 3} fontSize={10} fill="currentColor">{h.label} {fmt(h.value)}</text>
          </g>
        ))}
        {series.map((s, k) => {
          const pts = s.values.map((v, i) => (v === null || !Number.isFinite(v) ? null : [x(i), y(v)] as const));
          const path = pts.reduce((acc, p, i) => (p ? `${acc}${acc && pts[i - 1] ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}` : acc), "");
          return (
            <g key={s.label} stroke={PALETTE[k % PALETTE.length]} fill={PALETTE[k % PALETTE.length]}>
              {!s.points && <path d={path} fill="none" strokeWidth={1.5} />}
              {pts.map((p, i) => p && <circle key={i} cx={p[0]} cy={p[1]} r={2.4} />)}
            </g>
          );
        })}
        {xLabels && n <= 30 && xLabels.map((l, i) => (
          <text key={i} x={x(i)} y={H - 6} textAnchor="middle" fontSize={9} fill="currentColor">{l}</text>
        ))}
      </svg>
      {series.length > 1 && (
        <div className="mt-1 flex flex-wrap gap-3 text-[11px] text-ink-2">
          {series.map((s, k) => (
            <span key={s.label} className="inline-flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: PALETTE[k % PALETTE.length] }} />{s.label}
            </span>
          ))}
        </div>
      )}
    </figure>
  );
}

export function BarChart({ title, labels, values, refLines = [], unit = "" }: {
  title: string; labels: string[]; values: (number | null)[]; refLines?: HLine[]; unit?: string;
}) {
  const clean = values.filter((v): v is number => v !== null && Number.isFinite(v));
  if (!clean.length) return null;
  const hi = Math.max(...clean, ...refLines.map((r) => r.value ?? 0)) * 1.15 || 1;
  const W = 640;
  const H = 180;
  const L = 40;
  const B = 22;
  const T = 10;
  const bw = (W - L - 10) / values.length;
  const y = (v: number) => T + (H - T - B) * (1 - v / hi);
  return (
    <figure className="w-full">
      <figcaption className="mb-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-3">{title}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full text-ink-3" role="img" aria-label={title}>
        <line x1={L} x2={W - 10} y1={H - B} y2={H - B} stroke="currentColor" strokeOpacity={0.4} />
        {values.map((v, i) => v !== null && Number.isFinite(v) && (
          <g key={i}>
            <rect x={L + i * bw + bw * 0.18} y={y(v)} width={bw * 0.64} height={H - B - y(v)} fill={PALETTE[0]} rx={2} />
            <text x={L + i * bw + bw / 2} y={y(v) - 3} textAnchor="middle" fontSize={10} fill="currentColor">{fmt(v)}{unit}</text>
            <text x={L + i * bw + bw / 2} y={H - 6} textAnchor="middle" fontSize={10} fill="currentColor">{labels[i]}</text>
          </g>
        ))}
        {refLines.map((r, i) => typeof r.value === "number" && (
          <g key={i}>
            <line x1={L} x2={W - 10} y1={y(r.value)} y2={y(r.value)} stroke="#c0392b" strokeDasharray="4 3" />
            <text x={L + 2} y={y(r.value) - 2} fontSize={9} fill="#c0392b">{r.label}</text>
          </g>
        ))}
      </svg>
    </figure>
  );
}
