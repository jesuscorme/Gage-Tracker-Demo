// MSA report panels drawn with plain SVG: the chart types used in automotive MSA reports
// (components of variation, R / X̄ by operator, measurement by part and operator, interaction,
// linearity and bias, stability, type 1 run chart, attribute agreement intervals).
// Values come from the engine results; only presentation summaries (box-plot quartiles,
// nested R / X̄ limits with the AIAG SPC constants) are derived here from the stored observations.

import type { ReactNode } from "react";
import { useI18n } from "@/lib/i18n";
import type { MsaObservationRow, MsaRun } from "@/lib/types-b3";

const C = {
  a: "#0b63c1", b: "#e07b22", c: "#16815a", d: "#8b3fa8", e: "#5d6878",
  limit: "#c0262d", center: "#16815a", ref: "#0f1722", grid: "#e6e9ef", axis: "#9aa3af", dot: "#b4bcc8",
};
const SERIES = [C.a, C.b, C.c, C.d, C.e];

// AIAG SPC Manual 2nd ed., Appendix E (subgroup size n = 2..10).
const A2: Record<number, number> = { 2: 1.88, 3: 1.023, 4: 0.729, 5: 0.577, 6: 0.483, 7: 0.419, 8: 0.373, 9: 0.337, 10: 0.308 };
const D3: Record<number, number> = { 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0.076, 8: 0.136, 9: 0.184, 10: 0.223 };
const D4: Record<number, number> = { 2: 3.267, 3: 2.574, 4: 2.282, 5: 2.114, 6: 2.004, 7: 1.924, 8: 1.864, 9: 1.816, 10: 1.777 };

type Num = number | null | undefined;
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const mean = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / xs.length;

/** Limits and reference values: five significant digits, no trailing zeros. */
const lim = (v: number) => Number(v.toPrecision(5)).toString();

function tickDecimals(ticks: number[]) {
  const step = ticks.length > 1 ? Math.abs(ticks[1] - ticks[0]) : Math.abs(ticks[0]) || 1;
  for (let d = 0; d <= 8; d++) if (Math.abs(Math.round(step * 10 ** d) - step * 10 ** d) < 1e-6) return d;
  return 8;
}

function niceTicks(lo: number, hi: number, count = 5): number[] {
  const span = hi - lo || 1;
  const step0 = span / count;
  const mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= count + 0.5) ?? 10 * mag;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(Math.abs(v) < step * 1e-9 ? 0 : v);
  return out;
}

function domain(values: Num[], pad = 0.08, zero = false): [number, number] {
  const xs = values.filter(isNum);
  if (!xs.length) return [0, 1];
  let lo = Math.min(...xs);
  let hi = Math.max(...xs);
  if (zero) lo = Math.min(lo, 0);
  if (lo === hi) { lo -= Math.abs(lo) * 0.1 || 1; hi += Math.abs(hi) * 0.1 || 1; }
  const p = (hi - lo) * pad;
  return [zero && lo >= 0 ? 0 : lo - p, hi + p];
}

// ------------------------------------------------------------------ frame

interface Frame { x: (v: number) => number; y: (v: number) => number; L: number; R: number; T: number; B: number; W: number; H: number }

function Plot({ title, yLabel, xLabel, y: [y0, y1], xCount, xNumeric, xTicks, height = 250, right = 70, width = 560, legend, children }: {
  title: string; yLabel?: string; xLabel?: string; y: [number, number]; xCount?: number; xNumeric?: [number, number];
  xTicks?: { at: number; label: string }[]; height?: number; right?: number; width?: number; legend?: { label: string; color: string; shape?: Shape; dashed?: boolean }[];
  children: (f: Frame) => ReactNode;
}) {
  const W = width, H = height, L = 58, T = 14, B = xLabel ? 44 : 30, R = right;
  const x = xNumeric
    ? (v: number) => L + ((W - L - R) * (v - xNumeric[0])) / (xNumeric[1] - xNumeric[0] || 1)
    : (i: number) => L + ((W - L - R) * (i + 0.5)) / Math.max(1, xCount ?? 1);
  const y = (v: number) => T + (H - T - B) * (1 - (v - y0) / (y1 - y0 || 1));
  const yt = niceTicks(y0, y1);
  const dec = tickDecimals(yt);
  return (
    <figure className="rounded-lg border border-line bg-surface p-3">
      <figcaption className="mb-1 text-[13px] font-semibold text-ink">{title}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={title}>
        {yt.map((v) => (
          <g key={v}>
            <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} stroke={C.grid} />
            <text x={L - 6} y={y(v) + 3.5} textAnchor="end" fontSize={10} fill={C.e}>{v.toFixed(dec)}</text>
          </g>
        ))}
        <line x1={L} x2={L} y1={T} y2={H - B} stroke={C.axis} />
        <line x1={L} x2={W - R} y1={H - B} y2={H - B} stroke={C.axis} />
        {xTicks?.map((t, i) => (
          <text key={i} x={x(t.at)} y={H - B + 13} textAnchor="middle" fontSize={9.5} fill={C.e}>{t.label}</text>
        ))}
        {yLabel && <text transform={`translate(13 ${(T + H - B) / 2}) rotate(-90)`} textAnchor="middle" fontSize={10.5} fill={C.e}>{yLabel}</text>}
        {xLabel && <text x={(L + W - R) / 2} y={H - 6} textAnchor="middle" fontSize={10.5} fill={C.e}>{xLabel}</text>}
        {children({ x, y, L, R, T, B, W, H })}
      </svg>
      {legend && legend.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-ink-2">
          {legend.map((l) => (
            <span key={l.label} className="inline-flex items-center gap-1.5">
              <svg width="18" height="10" aria-hidden>
                {l.shape ? <Marker shape={l.shape} cx={9} cy={5} r={3.6} color={l.color} />
                  : <line x1={1} x2={17} y1={5} y2={5} stroke={l.color} strokeWidth={2} strokeDasharray={l.dashed ? "4 3" : undefined} />}
              </svg>{l.label}
            </span>
          ))}
        </div>
      )}
    </figure>
  );
}

type Shape = "circle" | "square" | "diamond" | "triangle" | "cross";
const SHAPES: Shape[] = ["circle", "square", "diamond", "triangle", "cross"];

function Marker({ shape, cx, cy, r = 3, color, fill }: { shape: Shape; cx: number; cy: number; r?: number; color: string; fill?: string }) {
  const f = fill ?? color;
  if (shape === "square") return <rect x={cx - r} y={cy - r} width={2 * r} height={2 * r} fill={f} stroke={color} />;
  if (shape === "diamond") return <path d={`M${cx},${cy - r * 1.3}L${cx + r * 1.3},${cy}L${cx},${cy + r * 1.3}L${cx - r * 1.3},${cy}Z`} fill={f} stroke={color} />;
  if (shape === "triangle") return <path d={`M${cx},${cy - r * 1.3}L${cx + r * 1.2},${cy + r}L${cx - r * 1.2},${cy + r}Z`} fill={f} stroke={color} />;
  if (shape === "cross") return <path d={`M${cx - r},${cy - r}L${cx + r},${cy + r}M${cx + r},${cy - r}L${cx - r},${cy + r}`} stroke={color} strokeWidth={1.6} />;
  return <circle cx={cx} cy={cy} r={r} fill={f} stroke={color} />;
}

function polyline(pts: ([number, number] | null)[]) {
  let d = "";
  pts.forEach((p, i) => { if (p) d += `${d && pts[i - 1] ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`; });
  return d;
}

interface Rule { value: Num; label?: string; color: string; dashed?: boolean }

/** Horizontal reference lines with their labels on the right, pushed apart so they never overlap. */
function Rules({ f, rules }: { f: Frame; rules: Rule[] }) {
  const shown = rules.filter((r): r is Rule & { value: number } => isNum(r.value));
  const labels = shown.filter((r) => r.label).map((r) => ({ r, y: f.y(r.value) })).sort((a, b) => a.y - b.y);
  for (let i = 1; i < labels.length; i++) if (labels[i].y - labels[i - 1].y < 12) labels[i].y = labels[i - 1].y + 12;
  return (
    <g>
      {shown.map((r, i) => <line key={i} x1={f.L} x2={f.W - f.R} y1={f.y(r.value)} y2={f.y(r.value)} stroke={r.color} strokeWidth={1.3}
        strokeDasharray={r.dashed === false ? undefined : "5 3"} />)}
      {labels.map(({ r, y }, i) => <text key={i} x={f.W - f.R + 5} y={y + 3.5} fontSize={10} fill={r.color}>{r.label}</text>)}
    </g>
  );
}

function HRule({ f, value, label, color, dashed = true }: { f: Frame; value: Num; label?: string; color: string; dashed?: boolean }) {
  if (!isNum(value)) return null;
  return (
    <g>
      <line x1={f.L} x2={f.W - f.R} y1={f.y(value)} y2={f.y(value)} stroke={color} strokeWidth={1.3} strokeDasharray={dashed ? "5 3" : undefined} />
      {label && <text x={f.W - f.R + 5} y={f.y(value) + 3.5} fontSize={10} fill={color}>{label}</text>}
    </g>
  );
}

// ------------------------------------------------------------------ generic MSA charts

/** Grouped bars: %Contribution and %Study Var for GRR, repeatability, reproducibility and part-to-part. */
function ComponentsChart({ components }: { components: { source: string; pct_contribution: Num; pct_study_var: Num; pct_tolerance?: Num }[] }) {
  const { t } = useI18n();
  const order: [string, string][] = [["GRR", t("mc.grr")], ["EV", t("mc.repeat")], ["AV", t("mc.reprod")], ["PV", t("mc.part")]];
  const rows = order.map(([k, label]) => ({ label, row: components.find((c) => c.source === k) }));
  const hasTol = rows.some((r) => isNum(r.row?.pct_tolerance));
  const keys: { key: "pct_contribution" | "pct_study_var" | "pct_tolerance"; label: string; color: string }[] = [
    { key: "pct_contribution", label: t("mc.pctContribution"), color: C.a },
    { key: "pct_study_var", label: t("mc.pctStudyVar"), color: C.b },
    ...(hasTol ? [{ key: "pct_tolerance" as const, label: t("mc.pctTolerance"), color: C.c }] : []),
  ];
  const hi = Math.max(100, ...rows.flatMap((r) => keys.map((k) => r.row?.[k.key]).filter(isNum)));
  return (
    <Plot title={t("mc.components")} yLabel={t("mc.percent")} y={[0, hi * 1.05]} xCount={rows.length} right={14}
      xTicks={rows.map((r, i) => ({ at: i, label: r.label }))} legend={keys.map((k) => ({ label: k.label, color: k.color, shape: "square" as const }))}>
      {(f) => {
        const slot = (f.W - f.L - f.R) / rows.length;
        const bw = (slot * 0.7) / keys.length;
        return (
          <>
            {[10, 30].map((v) => <HRule key={v} f={f} value={v} color={C.e} />)}
            {rows.map((r, i) => keys.map((k, j) => {
              const v = r.row?.[k.key];
              if (!isNum(v)) return null;
              const x0 = f.x(i) - (bw * keys.length) / 2 + j * bw;
              return (
                <g key={`${i}-${j}`}>
                  <rect x={x0 + 1} y={f.y(v)} width={bw - 2} height={f.y(0) - f.y(v)} fill={k.color} rx={2} />
                  <text x={x0 + bw / 2} y={f.y(v) - 3} textAnchor="middle" fontSize={8.5} fill={C.e}>{v.toFixed(1)}</text>
                </g>
              );
            }))}
          </>
        );
      }}
    </Plot>
  );
}

/** Control chart split into one segment per operator (R or X̄ by operator). */
function SegmentedChart({ title, yLabel, groups, center, ucl, lcl, centerLabel, flagOutside = true }: {
  title: string; yLabel: string; groups: { label: string; xLabels: string[]; values: Num[] }[];
  center: Num; ucl: Num; lcl: Num; centerLabel: string; flagOutside?: boolean;
}) {
  const { t } = useI18n();
  const flat = groups.flatMap((g) => g.values);
  const n = flat.length;
  const [y0, y1] = domain([...flat, ucl, lcl, center], 0.12);
  const ticks: { at: number; label: string }[] = [];
  let k = 0;
  for (const g of groups) { g.xLabels.forEach((l, i) => { if (n <= 45 || i % 2 === 0) ticks.push({ at: k + i, label: l }); }); k += g.values.length; }
  return (
    <Plot title={title} yLabel={yLabel} xLabel={t("mc.partLabel")} y={[y0, y1]} xCount={n} xTicks={ticks}>
      {(f) => {
        let start = 0;
        const segs = groups.map((g) => { const s = start; start += g.values.length; return { g, s }; });
        const out = (v: number) => flagOutside && ((isNum(ucl) && v > ucl) || (isNum(lcl) && v < lcl));
        return (
          <>
            <Rules f={f} rules={[
              { value: ucl, label: isNum(ucl) ? `${t("mc.ucl")} ${lim(ucl)}` : "", color: C.limit },
              { value: center, label: isNum(center) ? `${centerLabel} ${lim(center)}` : "", color: C.center, dashed: false },
              { value: lcl, label: isNum(lcl) ? `${t("mc.lcl")} ${lim(lcl)}` : "", color: C.limit },
            ]} />
            {segs.map(({ g, s }, gi) => (
              <g key={g.label}>
                {gi > 0 && <line x1={f.x(s - 0.5)} x2={f.x(s - 0.5)} y1={f.T} y2={f.H - f.B} stroke={C.axis} strokeDasharray="3 3" />}
                <text x={f.x(s - 0.5) + 4} y={f.T + 10} fontSize={10} fontWeight={600} fill={C.ref}>{g.label}</text>
                <path d={polyline(g.values.map((v, i) => (isNum(v) ? [f.x(s + i), f.y(v)] : null)))} fill="none" stroke={C.a} strokeWidth={1.3} />
                {g.values.map((v, i) => isNum(v) && (
                  <Marker key={i} shape={out(v) ? "square" : "circle"} cx={f.x(s + i)} cy={f.y(v)} r={out(v) ? 3.4 : 2.6} color={out(v) ? C.limit : C.a} />
                ))}
              </g>
            ))}
          </>
        );
      }}
    </Plot>
  );
}

/** Every reading (light dots) and the mean per category joined by a line. */
function DotMeanChart({ title, xLabel, yLabel, categories, readings, groupBreaks }: {
  title: string; xLabel: string; yLabel: string; categories: string[]; readings: number[][]; groupBreaks?: { at: number; label: string }[];
}) {
  const { t } = useI18n();
  const means = readings.map((r) => (r.length ? mean(r) : null));
  const [y0, y1] = domain(readings.flat(), 0.1);
  return (
    <Plot title={title} xLabel={xLabel} yLabel={yLabel} y={[y0, y1]} xCount={categories.length}
      xTicks={categories.map((c, i) => ({ at: i, label: c }))}
      legend={[{ label: t("mc.readings"), color: C.dot, shape: "circle" }, { label: t("mc.mean"), color: C.a, shape: "diamond" }]}>
      {(f) => (
        <>
          {groupBreaks?.map((g, i) => (
            <g key={g.label}>
              {i > 0 && <line x1={f.x(g.at - 0.5)} x2={f.x(g.at - 0.5)} y1={f.T} y2={f.H - f.B} stroke={C.axis} strokeDasharray="3 3" />}
              <text x={f.x(g.at - 0.5) + 4} y={f.T + 10} fontSize={10} fontWeight={600} fill={C.ref}>{g.label}</text>
            </g>
          ))}
          {readings.map((r, i) => r.map((v, j) => <circle key={`${i}-${j}`} cx={f.x(i)} cy={f.y(v)} r={2.6} fill={C.dot} fillOpacity={0.75} />))}
          {groupBreaks ? groupBreaks.map((g, gi) => {
            const end = groupBreaks[gi + 1]?.at ?? categories.length;
            return <path key={g.label} d={polyline(means.slice(g.at, end).map((m, k) => (isNum(m) ? [f.x(g.at + k), f.y(m)] : null)))} fill="none" stroke={C.a} strokeWidth={1.5} />;
          }) : <path d={polyline(means.map((m, i) => (isNum(m) ? [f.x(i), f.y(m)] : null)))} fill="none" stroke={C.a} strokeWidth={1.5} />}
          {means.map((m, i) => isNum(m) && <Marker key={i} shape="diamond" cx={f.x(i)} cy={f.y(m)} r={3.2} color={C.a} />)}
        </>
      )}
    </Plot>
  );
}

function quartiles(xs: number[]) {
  const s = [...xs].sort((a, b) => a - b);
  const q = (p: number) => { const h = (s.length - 1) * p; const lo = Math.floor(h); return s[lo] + (s[Math.ceil(h)] - s[lo]) * (h - lo); };
  const q1 = q(0.25), q3 = q(0.75), iqr = q3 - q1;
  const inside = s.filter((v) => v >= q1 - 1.5 * iqr && v <= q3 + 1.5 * iqr);
  return { q1, med: q(0.5), q3, lo: inside[0], hi: inside[inside.length - 1], outliers: s.filter((v) => v < q1 - 1.5 * iqr || v > q3 + 1.5 * iqr) };
}

/** Box plot of all readings per operator with the operator means joined. */
function BoxChart({ title, xLabel, yLabel, labels, values }: { title: string; xLabel: string; yLabel: string; labels: string[]; values: number[][] }) {
  const { t } = useI18n();
  const boxes = values.map((v) => (v.length ? quartiles(v) : null));
  const means = values.map((v) => (v.length ? mean(v) : null));
  const [y0, y1] = domain(values.flat(), 0.1);
  return (
    <Plot title={title} xLabel={xLabel} yLabel={yLabel} y={[y0, y1]} xCount={labels.length} right={20}
      xTicks={labels.map((l, i) => ({ at: i, label: l }))} legend={[{ label: t("mc.mean"), color: C.b, shape: "diamond" }]}>
      {(f) => {
        const bw = Math.min(60, ((f.W - f.L - f.R) / labels.length) * 0.45);
        return (
          <>
            {boxes.map((b, i) => b && (
              <g key={i}>
                <line x1={f.x(i)} x2={f.x(i)} y1={f.y(b.hi)} y2={f.y(b.q3)} stroke={C.e} />
                <line x1={f.x(i)} x2={f.x(i)} y1={f.y(b.q1)} y2={f.y(b.lo)} stroke={C.e} />
                <line x1={f.x(i) - bw / 4} x2={f.x(i) + bw / 4} y1={f.y(b.hi)} y2={f.y(b.hi)} stroke={C.e} />
                <line x1={f.x(i) - bw / 4} x2={f.x(i) + bw / 4} y1={f.y(b.lo)} y2={f.y(b.lo)} stroke={C.e} />
                <rect x={f.x(i) - bw / 2} y={f.y(b.q3)} width={bw} height={Math.max(1, f.y(b.q1) - f.y(b.q3))} fill={C.a} fillOpacity={0.18} stroke={C.a} rx={2} />
                <line x1={f.x(i) - bw / 2} x2={f.x(i) + bw / 2} y1={f.y(b.med)} y2={f.y(b.med)} stroke={C.a} strokeWidth={2} />
                {b.outliers.map((o, k) => <Marker key={k} shape="cross" cx={f.x(i)} cy={f.y(o)} r={2.6} color={C.limit} />)}
              </g>
            ))}
            <path d={polyline(means.map((m, i) => (isNum(m) ? [f.x(i), f.y(m)] : null)))} fill="none" stroke={C.b} strokeWidth={1.4} />
            {means.map((m, i) => isNum(m) && <Marker key={i} shape="diamond" cx={f.x(i)} cy={f.y(m)} r={3.4} color={C.b} />)}
          </>
        );
      }}
    </Plot>
  );
}

/** Part × operator interaction: average per part, one line and marker shape per operator. */
function InteractionChart({ operators, parts, values }: { operators: string[]; parts: string[]; values: Num[][] }) {
  const { t } = useI18n();
  const [y0, y1] = domain(values.flat(), 0.1);
  return (
    <Plot title={t("mc.interaction")} xLabel={t("mc.partLabel")} yLabel={t("mc.average")} y={[y0, y1]} xCount={parts.length} right={20}
      xTicks={parts.map((p, i) => ({ at: i, label: p }))}
      legend={operators.map((o, k) => ({ label: o, color: SERIES[k % SERIES.length], shape: SHAPES[k % SHAPES.length] }))}>
      {(f) => operators.map((o, k) => {
        const color = SERIES[k % SERIES.length];
        return (
          <g key={o}>
            <path d={polyline(values[k].map((v, i) => (isNum(v) ? [f.x(i), f.y(v)] : null)))} fill="none" stroke={color} strokeWidth={1.5}
              strokeDasharray={k === 2 ? "5 3" : k === 1 ? "8 2" : undefined} />
            {values[k].map((v, i) => isNum(v) && <Marker key={i} shape={SHAPES[k % SHAPES.length]} cx={f.x(i)} cy={f.y(v)} r={3.2} color={color} />)}
          </g>
        );
      })}
    </Plot>
  );
}

// ------------------------------------------------------------------ helpers over raw observations

function cellsByOperatorPart(obs: MsaObservationRow[]) {
  const map = new Map<string, Map<string, number[]>>();
  for (const o of obs) {
    const v = Number(o.value);
    if (!o.operator || o.part === undefined || !Number.isFinite(v)) continue;
    if (!map.has(o.operator)) map.set(o.operator, new Map());
    const parts = map.get(o.operator)!;
    const key = String(o.part);
    if (!parts.has(key)) parts.set(key, []);
    parts.get(key)!.push(v);
  }
  return map;
}

// ------------------------------------------------------------------ per family

function GrrCrossed({ run }: { run: MsaRun }) {
  const { t } = useI18n();
  const r = run.results;
  const ch = r.charts;
  const ops: string[] = ch.range_chart.operators;
  const parts: string[] = ch.range_chart.parts;
  const cells = cellsByOperatorPart(run.observations);
  const byPart = parts.map((p) => ops.flatMap((o) => cells.get(o)?.get(String(p)) ?? []));
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <ComponentsChart components={r.tables.components} />
      <DotMeanChart title={t("mc.byPart")} xLabel={t("mc.partLabel")} yLabel={t("mc.measurement")} categories={parts} readings={byPart} />
      <SegmentedChart title={t("mc.rByOperator")} yLabel={t("mc.range")} centerLabel="R̄"
        groups={ops.map((o, i) => ({ label: o, xLabels: parts, values: ch.range_chart.values[i] }))}
        center={ch.range_chart.center} ucl={ch.range_chart.ucl} lcl={ch.range_chart.lcl} />
      <BoxChart title={t("mc.byOperator")} xLabel={t("mc.operator")} yLabel={t("mc.measurement")} labels={ch.by_operator.operators} values={ch.by_operator.values} />
      <SegmentedChart title={t("mc.xbarByOperator")} yLabel={t("mc.mean")} centerLabel="X̿" flagOutside={false}
        groups={ops.map((o, i) => ({ label: o, xLabels: parts, values: ch.average_chart.values[i] }))}
        center={ch.average_chart.center} ucl={ch.average_chart.ucl} lcl={ch.average_chart.lcl} />
      <InteractionChart operators={ch.interaction.operators} parts={ch.interaction.parts} values={ch.interaction.values} />
    </div>
  );
}

function GrrNested({ run }: { run: MsaRun }) {
  const { t } = useI18n();
  const r = run.results;
  const ops: string[] = r.charts.by_operator.operators;
  const cells = cellsByOperatorPart(run.observations);
  const groups = ops.map((o) => {
    const parts = [...(cells.get(o)?.keys() ?? [])];
    const readings = parts.map((p) => cells.get(o)!.get(p)!);
    return { o, parts, readings, ranges: readings.map((x) => Math.max(...x) - Math.min(...x)), means: readings.map(mean) };
  });
  const allRanges = groups.flatMap((g) => g.ranges);
  const n = groups[0]?.readings[0]?.length ?? 0;
  const rbar = allRanges.length ? mean(allRanges) : null;
  const xbb = run.observations.length ? mean(run.observations.map((o) => Number(o.value)).filter(Number.isFinite)) : null;
  const lim = isNum(rbar) && A2[n] !== undefined;
  let k = 0;
  const breaks = groups.map((g) => { const at = k; k += g.parts.length; return { at, label: g.o }; });
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <ComponentsChart components={r.tables.components} />
      <DotMeanChart title={t("mc.byPartNested")} xLabel={t("mc.partLabel")} yLabel={t("mc.measurement")}
        categories={groups.flatMap((g) => g.parts)} readings={groups.flatMap((g) => g.readings)} groupBreaks={breaks} />
      <SegmentedChart title={t("mc.rByOperator")} yLabel={t("mc.range")} centerLabel="R̄"
        groups={groups.map((g) => ({ label: g.o, xLabels: g.parts, values: g.ranges }))}
        center={rbar} ucl={lim ? D4[n] * rbar! : null} lcl={lim ? D3[n] * rbar! : null} />
      <BoxChart title={t("mc.byOperator")} xLabel={t("mc.operator")} yLabel={t("mc.measurement")} labels={ops} values={r.charts.by_operator.values} />
      <SegmentedChart title={t("mc.xbarByOperator")} yLabel={t("mc.mean")} centerLabel="X̿" flagOutside={false}
        groups={groups.map((g) => ({ label: g.o, xLabels: g.parts, values: g.means }))}
        center={xbb} ucl={lim && isNum(xbb) ? xbb + A2[n] * rbar! : null} lcl={lim && isNum(xbb) ? xbb - A2[n] * rbar! : null} />
    </div>
  );
}

function StatTable({ title, rows }: { title: string; rows: [string, ReactNode][] }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-3">
      <div className="mb-1.5 text-[12px] font-semibold text-ink">{title}</div>
      <table className="w-full text-[12px]"><tbody>
        {rows.map(([k, v]) => <tr key={k}><td className="py-0.5 pr-3 text-ink-3">{k}</td><td className="py-0.5 text-right font-mono tabular-nums">{v}</td></tr>)}
      </tbody></table>
    </div>
  );
}

const pval = (v: Num) => (isNum(v) ? (v < 0.001 ? "< 0.001" : v.toFixed(3)) : "—");
const sig = (v: Num, d = 4) => (isNum(v) ? (Math.abs(v) >= 1000 ? v.toFixed(1) : Number(v.toPrecision(d)).toString()) : "—");

function Linearity({ run }: { run: MsaRun }) {
  const { t } = useI18n();
  const r = run.results;
  const ch = r.charts;
  const m = r.metrics;
  const reg = r.tables.regression;
  const pts = ch.points as { reference: number; bias: number }[];
  const bands = ch.bands as { reference: number; fit: number; lower: number; upper: number }[];
  const avgs = ch.averages as { reference: number; average_bias: number; n: number }[];
  const xs = [...pts.map((p) => p.reference), ...bands.map((b) => b.reference)];
  const [x0, x1] = domain(xs, 0.06);
  const [y0, y1] = domain([...pts.map((p) => p.bias), ...bands.flatMap((b) => [b.lower, b.upper]), 0], 0.1);
  const xt = niceTicks(x0, x1);
  const byRef = new Map<number, { sum: number; n: number }>();
  for (const a of avgs) { const e = byRef.get(a.reference) ?? { sum: 0, n: 0 }; e.sum += a.average_bias * a.n; e.n += a.n; byRef.set(a.reference, e); }
  return (
    <div className="grid gap-3 lg:grid-cols-[3fr_2fr]">
      <Plot title={t("mc.linearity")} xLabel={t("mc.reference")} yLabel={t("mc.bias")} y={[y0, y1]} xNumeric={[x0, x1]} height={300} right={20}
        xTicks={xt.map((v) => ({ at: v, label: v.toFixed(tickDecimals(xt)) }))}
        legend={[{ label: t("mc.regression"), color: C.limit }, { label: t("mc.ci95"), color: C.c, dashed: true },
          { label: t("mc.data"), color: C.a, shape: "circle" }, { label: t("mc.avgBias"), color: C.b, shape: "square" }]}>
        {(f) => (
          <>
            <HRule f={f} value={0} label="" color={C.ref} />
            <path d={polyline(bands.map((b) => [f.x(b.reference), f.y(b.upper)]))} fill="none" stroke={C.c} strokeDasharray="5 3" strokeWidth={1.4} />
            <path d={polyline(bands.map((b) => [f.x(b.reference), f.y(b.lower)]))} fill="none" stroke={C.c} strokeDasharray="5 3" strokeWidth={1.4} />
            <path d={polyline(bands.map((b) => [f.x(b.reference), f.y(b.fit)]))} fill="none" stroke={C.limit} strokeWidth={2.2} />
            {pts.map((p, i) => <circle key={i} cx={f.x(p.reference)} cy={f.y(p.bias)} r={2.8} fill={C.a} fillOpacity={0.8} />)}
            {[...byRef].map(([ref, e]) => <Marker key={ref} shape="square" cx={f.x(ref)} cy={f.y(e.sum / e.n)} r={3.6} color={C.b} />)}
          </>
        )}
      </Plot>
      <div className="space-y-3">
        <StatTable title={t("mc.linearityTable")} rows={[
          [t("mc.constant"), <>{sig(reg.intercept)} <span className="text-ink-3">SE {sig(reg.se_intercept, 3)} · p {pval(m.intercept_p_value as Num)}</span></>],
          [t("mc.slope"), <>{sig(reg.slope)} <span className="text-ink-3">SE {sig(reg.se_slope, 3)} · p {pval(m.slope_p_value as Num)}</span></>],
          ["S", sig(reg.s)], ["R²", isNum(reg.r_squared) ? `${(reg.r_squared * 100).toFixed(1)} %` : "—"],
          [t("mc.pctLinearity"), isNum(m.pct_linearity) ? `${(m.pct_linearity as number).toFixed(2)} %` : "—"],
        ]} />
        <StatTable title={t("mc.biasTable")} rows={[
          [t("mc.overall"), sig(mean(pts.map((p) => p.bias)))],
          ...[...byRef].sort((a, b) => a[0] - b[0]).map(([ref, e]) => [`${t("mc.reference")} ${sig(ref)}`, sig(e.sum / e.n)] as [string, string]),
        ]} />
      </div>
    </div>
  );
}

function Stability({ run }: { run: MsaRun }) {
  const { t } = useI18n();
  const ch = run.results.charts;
  const loc = ch.location;
  const disp = ch.dispersion;
  const viol = new Map<number, string[]>();
  for (const v of (loc.violations ?? []) as { index: number; rule: string | number }[]) viol.set(v.index, [...(viol.get(v.index) ?? []), String(v.rule)]);
  const chart = (title: string, yLabel: string, values: Num[], center: Num, ucl: Num, lcl: Num, ref: Num, flags: (i: number, v: number) => string[] | null) => {
    const [y0, y1] = domain([...values, center, ucl, lcl, ref], 0.12);
    const labels = (loc.subgroups as (string | number)[]).map(String);
    return (
      <Plot title={title} yLabel={yLabel} xLabel={t("mc.subgroup")} y={[y0, y1]} xCount={values.length} height={250} width={1000} right={90}
        xTicks={labels.map((l, i) => ({ at: i, label: values.length > 30 && i % 2 ? "" : l }))}>
        {(f) => (
          <>
            <Rules f={f} rules={[
              { value: ucl, label: isNum(ucl) ? `${t("mc.ucl")} ${lim(ucl)}` : "", color: C.limit },
              { value: center, label: isNum(center) ? `${t("mc.cl")} ${lim(center)}` : "", color: C.center, dashed: false },
              { value: lcl, label: isNum(lcl) ? `${t("mc.lcl")} ${lim(lcl)}` : "", color: C.limit },
              { value: ref, label: isNum(ref) ? `${t("mc.ref")} ${lim(ref)}` : "", color: C.d },
            ]} />
            <path d={polyline(values.map((v, i) => (isNum(v) ? [f.x(i), f.y(v)] : null)))} fill="none" stroke={C.ref} strokeWidth={1.2} />
            {values.map((v, i) => {
              if (!isNum(v)) return null;
              const fl = flags(i, v);
              return (
                <g key={i}>
                  <Marker shape={fl ? "square" : "circle"} cx={f.x(i)} cy={f.y(v)} r={fl ? 3.6 : 2.6} color={fl ? C.limit : C.ref} />
                  {fl && fl.length > 0 && <text x={f.x(i)} y={f.y(v) - 7} textAnchor="middle" fontSize={9} fontWeight={700} fill={C.limit}>{fl.join(",")}</text>}
                </g>
              );
            })}
          </>
        )}
      </Plot>
    );
  };
  return (
    <div className="grid gap-3">
      {chart(t(loc.kind === "I" ? "mc.iChart" : "mc.xbarChart"), t(loc.kind === "I" ? "mc.individual" : "mc.mean"), loc.values, loc.center, loc.ucl, loc.lcl, loc.reference,
        (i) => viol.get(i) ?? null)}
      {chart(t(disp.kind === "MR" ? "mc.mrChart" : disp.kind === "S" ? "mc.sChart" : "mc.rChart"), t(disp.kind === "MR" ? "mc.movingRange" : disp.kind === "S" ? "mc.stdev" : "mc.range"), disp.values, disp.center, disp.ucl, disp.lcl ?? 0, null,
        (_, v) => (isNum(disp.ucl) && v > disp.ucl ? ["1"] : null))}
      <p className="text-[11px] text-ink-3">{t("mc.rulesNote")}</p>
    </div>
  );
}

function Type1({ run }: { run: MsaRun }) {
  const { t } = useI18n();
  const r = run.results;
  const ch = r.charts.run;
  const s = r.tables.summary;
  const d = r.design as { tolerance?: number; k_percent?: number; l_sigma?: number; reference?: number };
  const values = ch.values as number[];
  const [y0, y1] = domain([...values, ch.upper, ch.lower, ch.reference], 0.12);
  const k = d.k_percent ?? 20;
  return (
    <div className="grid gap-3">
      <Plot title={t("mc.runChart")} xLabel={t("mc.observation")} yLabel={t("mc.measurement")} y={[y0, y1]} xCount={values.length} height={280} width={1000} right={150}
        xTicks={values.map((_, i) => ({ at: i, label: values.length > 25 ? (i % 5 === 0 ? String(i + 1) : "") : String(i + 1) }))}>
        {(f) => (
          <>
            <Rules f={f} rules={[
              { value: ch.upper, label: `${t("mc.ref")} + ${k / 2} % Tol (${lim(ch.upper)})`, color: C.limit, dashed: false },
              { value: ch.reference, label: `${t("mc.ref")} ${lim(ch.reference)}`, color: C.center, dashed: false },
              { value: ch.mean, label: `${t("mc.mean")} ${lim(ch.mean)}`, color: C.b },
              { value: ch.lower, label: `${t("mc.ref")} − ${k / 2} % Tol (${lim(ch.lower)})`, color: C.limit, dashed: false },
            ]} />
            <path d={polyline(values.map((v, i) => [f.x(i), f.y(v)]))} fill="none" stroke={C.a} strokeWidth={1.2} />
            {values.map((v, i) => <circle key={i} cx={f.x(i)} cy={f.y(v)} r={2.4} fill={C.a} />)}
          </>
        )}
      </Plot>
      <div className="grid gap-3 sm:grid-cols-3">
        <StatTable title={t("mc.basicStats")} rows={[
          [t("mc.reference"), sig(d.reference ?? ch.reference)], [t("mc.mean"), sig(s.average)], [t("mc.stdev"), sig(s.s)],
          [`${d.l_sigma ?? 6} × ${t("mc.stdev")}`, sig((d.l_sigma ?? 6) * s.s)], [t("mc.tolerance"), sig(d.tolerance)],
        ]} />
        <StatTable title={t("mc.bias")} rows={[[t("mc.bias"), sig(s.bias)], ["t", sig(s.t)], [t("mc.pValue"), pval(s.p_value)]]} />
        <StatTable title={t("mc.capability")} rows={[["Cg", sig(r.metrics.cg as Num, 3)], ["Cgk", sig(r.metrics.cgk as Num, 3)],
          ["K / L", `${k} % / ${d.l_sigma ?? 6}`]]} />
      </div>
    </div>
  );
}

/** Percent agreement per appraiser with its confidence interval (one panel per comparison). */
function IntervalChart({ title, rows }: { title: string; rows: { operator: string; pct: Num; ci_low: Num; ci_high: Num }[] }) {
  const { t } = useI18n();
  const lo = Math.min(...rows.map((r) => r.ci_low).filter(isNum), 100);
  const y0 = Math.max(0, Math.floor((lo - 5) / 5) * 5);
  return (
    <Plot title={title} xLabel={t("mc.appraiser")} yLabel={t("mc.percent")} y={[y0, 101]} xCount={rows.length} right={20}
      xTicks={rows.map((r, i) => ({ at: i, label: r.operator }))}
      legend={[{ label: t("mc.percent"), color: C.a, shape: "circle" }, { label: t("mc.ci95"), color: C.limit, shape: "cross" }]}>
      {(f) => rows.map((r, i) => (
        <g key={r.operator}>
          {isNum(r.ci_low) && isNum(r.ci_high) && (
            <>
              <line x1={f.x(i)} x2={f.x(i)} y1={f.y(r.ci_low)} y2={f.y(r.ci_high)} stroke={C.limit} strokeWidth={1.6} />
              <Marker shape="cross" cx={f.x(i)} cy={f.y(r.ci_low)} r={4} color={C.limit} />
              <Marker shape="cross" cx={f.x(i)} cy={f.y(r.ci_high)} r={4} color={C.limit} />
            </>
          )}
          {isNum(r.pct) && <>
            <circle cx={f.x(i)} cy={f.y(r.pct)} r={4} fill={C.a} />
            <text x={f.x(i) + 8} y={f.y(r.pct) + 3.5} fontSize={9.5} fill={C.e}>{r.pct.toFixed(1)}</text>
          </>}
        </g>
      ))}
    </Plot>
  );
}

function Attribute({ run }: { run: MsaRun }) {
  const { t } = useI18n();
  const ag = run.results.charts.agreement;
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <IntervalChart title={t("mc.within")} rows={ag.within} />
      {ag.vs_reference?.length ? <IntervalChart title={t("mc.vsStandard")} rows={ag.vs_reference} /> : null}
    </div>
  );
}

function Bias({ run }: { run: MsaRun }) {
  const { t } = useI18n();
  const ch = run.results.charts;
  const s = run.results.tables.summary;
  const edges = ch.histogram.edges as number[];
  const counts = ch.histogram.counts as number[];
  const [x0, x1] = domain([...edges, ch.reference, ...(ch.ci as number[]).map((c) => c)], 0.04);
  const xt = niceTicks(x0, x1);
  return (
    <div className="grid gap-3 lg:grid-cols-[3fr_2fr]">
      <Plot title={t("mc.histogram")} xLabel={t("mc.measurement")} yLabel={t("mc.frequency")} y={[0, Math.max(...counts) * 1.15]} xNumeric={[x0, x1]} right={20}
        xTicks={xt.map((v) => ({ at: v, label: v.toFixed(tickDecimals(xt)) }))}
        legend={[{ label: t("mc.ref"), color: C.center }, { label: t("mc.ci95Mean"), color: C.b, dashed: true }]}>
        {(f) => (
          <>
            {counts.map((c, i) => (
              <rect key={i} x={f.x(edges[i]) + 1} y={f.y(c)} width={Math.max(1, f.x(edges[i + 1]) - f.x(edges[i]) - 2)} height={f.y(0) - f.y(c)} fill={C.a} fillOpacity={0.75} rx={1.5} />
            ))}
            <rect x={f.x(ch.ci[0])} y={f.T} width={Math.max(1, f.x(ch.ci[1]) - f.x(ch.ci[0]))} height={f.H - f.B - f.T} fill={C.b} fillOpacity={0.1} />
            {(ch.ci as number[]).map((c, i) => <line key={i} x1={f.x(c)} x2={f.x(c)} y1={f.T} y2={f.H - f.B} stroke={C.b} strokeDasharray="5 3" />)}
            <line x1={f.x(ch.reference)} x2={f.x(ch.reference)} y1={f.T} y2={f.H - f.B} stroke={C.center} strokeWidth={2} />
          </>
        )}
      </Plot>
      <StatTable title={t("mc.bias")} rows={[
        [t("mc.reference"), sig(ch.reference)], [t("mc.mean"), sig(s.average)], [t("mc.bias"), sig(s.bias)], [t("mc.stdev"), sig(s.s)],
        ["t", sig(s.t)], [t("mc.pValue"), pval(s.p_value)], [t("mc.ci95"), `${sig(s.ci_low)} … ${sig(s.ci_high)}`],
      ]} />
    </div>
  );
}

export function MsaCharts({ run }: { run: MsaRun }) {
  switch (run.method) {
    case "GRR_CROSSED_AR":
    case "GRR_CROSSED_ANOVA": return <GrrCrossed run={run} />;
    case "GRR_NESTED_ANOVA": return <GrrNested run={run} />;
    case "LINEARITY": return <Linearity run={run} />;
    case "STABILITY": return <Stability run={run} />;
    case "TYPE1": return <Type1 run={run} />;
    case "ATTRIBUTE_AGREEMENT": return <Attribute run={run} />;
    case "BIAS": return <Bias run={run} />;
    default: return null;
  }
}
