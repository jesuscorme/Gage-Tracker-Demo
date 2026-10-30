"use client";

import Link from "next/link";
import { useState } from "react";
import { Icon, type IconName } from "@/components/icons";
import { Button, EmptyState, ErrorState, Field, Input, LinkButton, Loading, Select, ToneBadge, type Tone } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { usePlants, useUsers } from "@/lib/lookups";
import { GAGE_STATUSES, PRIORITY_TONE, REQ_STATUS_TONE, STATUS_TONE } from "@/lib/status";
import type { AuditEvent, Department, GageStatus } from "@/lib/types";
import type { ServiceRequest } from "@/lib/types-modules";

type Series = { month: string; count: number }[];
interface Overview {
  as_of: string;
  period: { from: string; to: string; months: string[] };
  gages: {
    total: number; active: number; current: number; calibrated: number; due_soon: number; overdue: number;
    out_of_service: number; in_calibration: number; by_status: Record<GageStatus, number>;
    by_type: { type: string; name: string; count: number }[];
    compliance_by_plant: { plant: string; name: string; active: number; current: number; overdue: number; pct_current: number | null }[];
    upcoming: { id: string; gage_code: string; description: string; next_due_date: string | null; status: GageStatus }[];
  };
  calibration: { pending: number; in_process: number; released_in_period: number; released_by_month: Series;
    results_in_period: Record<string, number> } | null;
  laboratory: { requests_open: number; work_orders_open: number; work_orders_overdue: number;
    workload: { technician: string; open_orders: number; planned_hours: number }[];
    completed_by_month: Series; requests_by_month: Series } | null;
  msa: { open: number; completed: number; not_acceptable: number; by_status: Record<string, number>;
    by_method: Record<string, Record<string, number>> } | null;
  oot: { open: number; gages_restricted: number; by_status: Record<string, number>; detected_by_month: Series } | null;
  expirations: { standards_expiring?: number; standards_expired?: number; authorizations_expiring?: number;
    competency_records_expiring?: number } | null;
}
type F = Record<string, string>;
const DECISIONS = ["ACCEPTABLE", "CONDITIONAL", "NOT_ACCEPTABLE", "INCONCLUSIVE", "NO_CRITERIA", "NOT_CALCULATED"] as const;
const PERIODS = ["30", "90", "365", "ytd"] as const;
const AMBER = "#e0a100";
const TONE_VAR: Record<string, string> = { ok: "var(--color-ok)", warn: AMBER, bad: "var(--color-bad)", block: "var(--color-block)",
  info: "var(--color-info)", mute: "#b9c1cc" };
const TILE = { ok: "bg-ok-soft text-ok", warn: "bg-warn-soft text-warn", bad: "bg-bad-soft text-bad", info: "bg-info-soft text-info",
  block: "bg-block-soft text-block", accent: "bg-accent-soft text-accent", violet: "bg-[#f1ebfb] text-[#6d3fc0]" };
type TileTone = keyof typeof TILE;
const SHADOW = "shadow-[0_1px_2px_rgba(15,23,34,0.04)]";

const isoDay = (d: Date) => d.toISOString().slice(0, 10);
function periodRange(p: string): F {
  const to = new Date();
  const from = p === "ytd" ? new Date(to.getFullYear(), 0, 1) : new Date(to.getTime() - Number(p) * 86400000);
  return { date_from: isoDay(from), date_to: isoDay(to) };
}
const pct = (n: number, d: number) => (d ? Math.round((1000 * n) / d) / 10 : 0);
const daysBetween = (a: string, b: string) => Math.round((Date.parse(b) - Date.parse(a)) / 86400000);

function Panel({ title, action, children, flush, className }: {
  title: React.ReactNode; action?: React.ReactNode; children: React.ReactNode; flush?: boolean; className?: string;
}) {
  return (
    <section className={`rounded-xl border border-line bg-surface ${SHADOW} ${className ?? ""}`}>
      <header className="flex items-center justify-between gap-3 px-5 pt-4 pb-2">
        <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
        {action}
      </header>
      <div className={flush ? "pb-2" : "px-5 pb-5"}>{children}</div>
    </section>
  );
}

function Kpi({ href, icon, tone, label, value, share, sub }: {
  href: string; icon: IconName; tone: TileTone; label: string; value: number; share?: number; sub?: React.ReactNode;
}) {
  const color = ({ ok: "text-ok", bad: "text-bad", warn: "text-warn" } as Record<string, string>)[tone] ?? "text-ink";
  const bar = ({ ok: "bg-ok", bad: "bg-bad", warn: "bg-[#e0a100]" } as Record<string, string>)[tone];
  return (
    <Link href={href} className={`flex gap-3 rounded-xl border border-line bg-surface p-4 ${SHADOW} transition hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-md`}>
      <span className={`grid size-12 shrink-0 place-items-center rounded-xl ${TILE[tone]}`}><Icon name={icon} size={24} /></span>
      <div className="min-w-0 flex-1">
        <div className="text-[12.5px] leading-tight text-ink-2">{label}</div>
        <div className={`tabular text-[26px] font-semibold leading-tight ${value && share !== undefined ? color : "text-ink"}`}>{value.toLocaleString()}</div>
        {share !== undefined ? (
          <div className="mt-1 flex items-center gap-2">
            <span className={`tabular text-[12px] font-semibold ${color}`}>{share}%</span>
            <div className="h-1.5 flex-1 rounded-full bg-line-2"><div className={`h-1.5 rounded-full ${bar}`} style={{ width: `${Math.min(100, share)}%` }} /></div>
          </div>
        ) : sub && <div className="mt-0.5 text-[11.5px] leading-snug text-ink-3">{sub}</div>}
      </div>
    </Link>
  );
}

function Donut({ parts, total, label }: { parts: { value: number; color: string }[]; total: number; label: string }) {
  const R = 52;
  const C = 2 * Math.PI * R;
  let offset = 0;
  return (
    <svg viewBox="0 0 140 140" className="size-44 shrink-0" role="img" aria-label={`${label}: ${total}`}>
      <circle cx="70" cy="70" r={R} fill="none" stroke="var(--color-line-2)" strokeWidth="18" />
      {total > 0 && parts.filter((p) => p.value > 0).map((p, i) => {
        const len = (p.value / total) * C;
        const el = <circle key={i} cx="70" cy="70" r={R} fill="none" stroke={p.color} strokeWidth="18"
          strokeDasharray={`${len} ${C - len}`} strokeDashoffset={-offset} transform="rotate(-90 70 70)" />;
        offset += len;
        return el;
      })}
      <text x="70" y="70" textAnchor="middle" fill="var(--color-ink)" style={{ fontSize: 22, fontWeight: 600 }}>{total.toLocaleString()}</text>
      <text x="70" y="88" textAnchor="middle" fill="var(--color-ink-3)" style={{ fontSize: 10 }}>{label}</text>
    </svg>
  );
}

/** Monthly counts as grouped columns, with the value over each bar. */
function Columns({ months, series, lang }: { months: string[]; series: { label: string; color: string; values: number[] }[]; lang: string }) {
  const max = Math.max(1, ...series.flatMap((s) => s.values));
  const name = (m: string) => new Date(`${m}-01T12:00:00`).toLocaleString(lang === "es" ? "es-MX" : "en-US", { month: "short" });
  return (
    <figure>
      <div className="flex h-40 items-end gap-1.5 border-b border-line">
        {months.map((m, i) => (
          <div key={m} className="flex h-full flex-1 items-end justify-center gap-0.5">
            {series.map((s) => (
              <div key={s.label} className="flex h-full w-full max-w-7 flex-col justify-end" title={`${name(m)} · ${s.label}: ${s.values[i] ?? 0}`}>
                {!!s.values[i] && <span className="tabular mb-0.5 text-center text-[10.5px] text-ink-2">{s.values[i]}</span>}
                <div className="rounded-t-sm" style={{ height: `${(100 * (s.values[i] ?? 0)) / max}%`, background: s.color, minHeight: s.values[i] ? 3 : 0 }} />
              </div>
            ))}
          </div>
        ))}
      </div>
      <div className="mt-1 flex gap-1.5">{months.map((m) => <span key={m} className="flex-1 text-center text-[10.5px] capitalize text-ink-3">{name(m)}</span>)}</div>
      {series.length > 1 && <figcaption className="mt-2 flex flex-wrap gap-3 text-[11.5px] text-ink-2">
        {series.map((s) => <span key={s.label} className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm" style={{ background: s.color }} />{s.label}</span>)}
      </figcaption>}
    </figure>
  );
}

export default function DashboardPage() {
  const { t, fmtDate, fmtDateTime, lang } = useI18n();
  const [allAlerts, setAllAlerts] = useState(false);
  const { membership, can } = useAuth();
  const plants = usePlants();
  const users = useUsers();
  const types = useResource(() => api.get<{ id: string; code: string; name: string }[]>("/gage-types"));
  const [period, setPeriod] = useState("365");
  const [more, setMore] = useState(false);
  const [draft, setDraft] = useState<F>({});
  const [filters, setFilters] = useState<F>({});
  const depts = useResource(() => (draft.plant_id ? api.get<Department[]>("/departments", { plant_id: draft.plant_id }) : Promise.resolve([])), [draft.plant_id]);
  const data = useResource(() => api.get<Overview>("/dashboard/overview", filters), [JSON.stringify(filters)]);
  const requests = useResource(() => (can("lab:read") ? api.get<ServiceRequest[]>("/lab/requests") : Promise.resolve([] as ServiceRequest[])), []);
  const activity = useResource(() => (can("audit:read") ? api.get<{ items: AuditEvent[] }>("/audit-events", { limit: 6 })
    : Promise.resolve({ items: [] as AuditEvent[] })), []);
  const set = (k: string, v: string) => setDraft({ ...draft, [k]: v });
  const clean = (f: F) => Object.fromEntries(Object.entries(f).filter(([, v]) => v));
  /** Quick filters (plant, period, clicks on the charts) apply at once; the advanced panel applies with its button. */
  const applyNow = (patch: F) => { const next = { ...draft, ...patch }; setDraft(next); setFilters(clean(next)); };
  const choosePeriod = (p: string) => {
    setPeriod(p);
    if (p === "custom") setMore(true);
    else applyNow(periodRange(p));
  };
  const d = data.data;
  const months = d?.period.months ?? [];
  const exp = d?.expirations ?? {};
  const typeId = (code: string) => (types.data ?? []).find((x) => x.code === code)?.id ?? "";

  const alerts: { icon: IconName; tone: TileTone; title: string; sub: string; href: string }[] = [];
  if (d) {
    if (d.gages.overdue) alerts.push({ icon: "oot", tone: "bad", title: t("dx.al.overdue", { n: d.gages.overdue }), sub: t("dx.al.overdueSub"), href: "/gages?status=OVERDUE" });
    if (d.gages.due_soon) alerts.push({ icon: "calendar", tone: "warn", title: t("dx.al.dueSoon", { n: d.gages.due_soon }), sub: t("dx.al.dueSoonSub"), href: "/gages?status=DUE_SOON" });
    if (d.oot?.open) alerts.push({ icon: "oot", tone: "block", title: t("dx.al.oot", { n: d.oot.open }), sub: t("dx.al.ootSub", { n: d.oot.gages_restricted }), href: "/oot" });
    if (d.laboratory?.requests_open) alerts.push({ icon: "lab", tone: "info", title: t("dx.al.requests", { n: d.laboratory.requests_open }), sub: t("dx.al.requestsSub"), href: "/laboratory/requests" });
    if (d.laboratory?.work_orders_overdue) alerts.push({ icon: "wrench", tone: "bad", title: t("dx.al.woOverdue", { n: d.laboratory.work_orders_overdue }), sub: t("dx.al.woOverdueSub"), href: "/laboratory/work-orders" });
    if (d.calibration?.pending) alerts.push({ icon: "calibration", tone: "accent", title: t("dx.al.cal", { n: d.calibration.pending }), sub: t("dx.al.calSub", { n: d.calibration.in_process }), href: "/calibrations" });
    if (d.msa?.not_acceptable) alerts.push({ icon: "msa", tone: "violet", title: t("dx.al.msaNok", { n: d.msa.not_acceptable }), sub: t("dx.al.msaNokSub"), href: "/msa" });
    const std = (exp.standards_expiring ?? 0) + (exp.standards_expired ?? 0);
    if (std) alerts.push({ icon: "standards", tone: "warn", title: t("dx.al.std", { n: std }), sub: t("dx.al.stdSub"), href: "/standards" });
    const comp = (exp.authorizations_expiring ?? 0) + (exp.competency_records_expiring ?? 0);
    if (comp) alerts.push({ icon: "people", tone: "warn", title: t("dx.al.comp", { n: comp }), sub: t("dx.al.compSub"), href: "/competency" });
  }
  const recentRequests = (requests.data ?? [])
    .filter((r) => !filters.plant_id || r.plant_id === filters.plant_id)
    .sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 5);
  const viewAll = (href: string) => <Link href={href} className="text-[13px] font-medium text-accent hover:underline">{t("dx.viewAll")}</Link>;
  const secondary = d ? [
    { l: t("dx.kpi.oos"), v: d.gages.out_of_service, h: "/gages?status=OUT_OF_SERVICE" },
    d.calibration && { l: t("dx.kpi.calPending"), v: d.calibration.pending, h: "/calibrations" },
    d.calibration && { l: t("dx.kpi.calInProcess"), v: d.calibration.in_process, h: "/calibrations" },
    d.laboratory && { l: t("dx.kpi.woOpen"), v: d.laboratory.work_orders_open, h: "/laboratory/work-orders" },
    d.laboratory && { l: t("dx.kpi.woOverdue"), v: d.laboratory.work_orders_overdue, h: "/laboratory/work-orders" },
    d.oot && { l: t("dx.kpi.ootOpen"), v: d.oot.open, h: "/oot" },
    exp.standards_expiring !== undefined && { l: t("dx.kpi.stdExpiring"), v: exp.standards_expiring ?? 0, h: "/standards" },
    exp.authorizations_expiring !== undefined && { l: t("dx.kpi.compExpiring"),
      v: (exp.authorizations_expiring ?? 0) + (exp.competency_records_expiring ?? 0), h: "/competency" },
  ].filter((x): x is { l: string; v: number; h: string } => !!x) : [];

  return (
    <>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          {membership?.organization_name && <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-3">{membership.organization_name}</div>}
          <h1 className="text-[26px] font-semibold tracking-tight text-ink">{t("dx.title")}</h1>
          <p className="text-[13.5px] text-ink-3">{t("dx.subtitle")}{d && <> · {t("dx.asOf", { d: fmtDate(d.as_of), f: fmtDate(d.period.from), t: fmtDate(d.period.to) })}</>}</p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <Field label={t("dx.plant")}><Select value={draft.plant_id ?? ""} onChange={(e) => applyNow({ plant_id: e.target.value, department_id: "" })}>
            <option value="">{t("dx.allPlants")}</option>{plants.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</Select></Field>
          <Field label={t("dx.period")}><Select value={period} onChange={(e) => choosePeriod(e.target.value)}>
            {PERIODS.map((p) => <option key={p} value={p}>{t(`dx.p.${p}`)}</option>)}<option value="custom">{t("dx.p.custom")}</option></Select></Field>
          <Button variant={more ? "primary" : "ghost"} onClick={() => setMore(!more)}>{more ? t("dx.lessFilters") : t("dx.moreFilters")}</Button>
        </div>
      </div>

      {more && (
        <section className="mb-4 rounded-xl border border-line bg-surface p-4">
          <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-7 lg:items-end">
            <Field label={t("dx.department")}><Select value={draft.department_id ?? ""} disabled={!draft.plant_id} onChange={(e) => set("department_id", e.target.value)}>
              <option value="">{t("dx.all")}</option>{(depts.data ?? []).map((x) => <option key={x.id} value={x.id}>{x.code}</option>)}</Select></Field>
            <Field label={t("dx.type")}><Select value={draft.gage_type_id ?? ""} onChange={(e) => set("gage_type_id", e.target.value)}>
              <option value="">{t("dx.all")}</option>{(types.data ?? []).map((x) => <option key={x.id} value={x.id}>{x.code}</option>)}</Select></Field>
            <Field label={t("dx.status")}><Select value={draft.status ?? ""} onChange={(e) => set("status", e.target.value)}>
              <option value="">{t("dx.all")}</option>{GAGE_STATUSES.map((s) => <option key={s} value={s}>{t(`status.${s}`)}</option>)}</Select></Field>
            <Field label={t("dx.responsible")}><Select value={draft.responsible_id ?? ""} onChange={(e) => set("responsible_id", e.target.value)}>
              <option value="">{t("dx.all")}</option>{users.list.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}</Select></Field>
            <Field label={t("dx.from")}><Input type="date" value={draft.date_from ?? ""} onChange={(e) => { setPeriod("custom"); set("date_from", e.target.value); }} /></Field>
            <Field label={t("dx.to")}><Input type="date" value={draft.date_to ?? ""} onChange={(e) => { setPeriod("custom"); set("date_to", e.target.value); }} /></Field>
            <div className="flex gap-2">
              <Button variant="primary" onClick={() => setFilters(clean(draft))}>{t("dx.apply")}</Button>
              <Button variant="ghost" onClick={() => { setDraft({}); setFilters({}); setPeriod("365"); }}>{t("dx.reset")}</Button>
            </div>
          </div>
        </section>
      )}

      {data.error ? <ErrorState error={data.error} onRetry={data.reload} /> : !d ? <Loading /> : (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
            <Kpi href="/gages" icon="gauge" tone="accent" label={t("dx.k.total")} value={d.gages.total} sub={t("dx.k.totalSub", { n: d.gages.active })} />
            <Kpi href="/gages?status=CALIBRATED" icon="audit" tone="ok" label={t("dx.k.current")} value={d.gages.current} share={pct(d.gages.current, d.gages.active)} />
            <Kpi href="/gages?status=OVERDUE" icon="oot" tone="bad" label={t("dx.kpi.overdue")} value={d.gages.overdue} share={pct(d.gages.overdue, d.gages.active)} />
            <Kpi href="/gages?status=DUE_SOON" icon="calendar" tone="warn" label={t("dx.k.dueSoon")} value={d.gages.due_soon} share={pct(d.gages.due_soon, d.gages.active)} />
            {d.laboratory && <Kpi href="/laboratory/requests" icon="lab" tone="info" label={t("dx.k.lab")} value={d.laboratory.requests_open}
              sub={t("dx.k.labSub", { a: d.laboratory.work_orders_open, b: d.laboratory.work_orders_overdue })} />}
            {d.msa && <Kpi href="/msa" icon="msa" tone="violet" label={t("dx.k.msa")} value={d.msa.open}
              sub={t("dx.k.msaSub", { a: d.msa.completed, b: d.msa.not_acceptable })} />}
          </div>

          {d.gages.total === 0 ? (
            <section className="rounded-xl border border-line bg-surface"><EmptyState action={!Object.keys(filters).length && can("gages:create") &&
              <LinkButton href="/gages/new" variant="primary">+ {t("gages.new")}</LinkButton>}>
              {Object.keys(filters).length ? t("dx.noData") : t("dashboard.empty")}</EmptyState></section>
          ) : (
            <>
              <div className="grid gap-4 xl:grid-cols-3">
                <Panel title={t("dx.statusTitle")}>
                  <div className="flex flex-col items-center gap-4 sm:flex-row">
                    <Donut total={d.gages.total} label={t("dx.k.totalShort")}
                      parts={GAGE_STATUSES.map((s) => ({ value: d.gages.by_status[s] ?? 0, color: TONE_VAR[STATUS_TONE[s]] }))} />
                    <ul className="w-full space-y-0.5">
                      {GAGE_STATUSES.map((s) => {
                        const n = d.gages.by_status[s] ?? 0;
                        const active = filters.status === s;
                        return (
                          <li key={s}>
                            <button type="button" onClick={() => applyNow({ status: active ? "" : s })} title={t("dx.clickFilter")}
                              className={`flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-[13px] hover:bg-line-2 ${active ? "bg-accent-soft" : ""}`}>
                              <span className="size-2.5 shrink-0 rounded-full" style={{ background: TONE_VAR[STATUS_TONE[s]] }} />
                              <span className="flex-1 text-ink-2">{t(`status.${s}`)}</span>
                              <span className="tabular font-medium text-ink">{n}</span>
                              <span className="tabular w-14 text-right text-[12px] text-ink-3">({pct(n, d.gages.total)}%)</span>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                </Panel>

                <Panel title={t("dx.ch.type")} action={viewAll("/settings/gage-types")}>
                  {!d.gages.by_type.length ? <EmptyState>—</EmptyState> : (
                    <ul className="space-y-2.5">
                      {d.gages.by_type.map((x, i) => {
                        const max = Math.max(...d.gages.by_type.map((y) => y.count));
                        const id = typeId(x.type);
                        const active = !!id && filters.gage_type_id === id;
                        return (
                          <li key={x.type}>
                            <button type="button" disabled={!id} onClick={() => applyNow({ gage_type_id: active ? "" : id })} title={t("dx.clickFilter")}
                              className="group grid w-full grid-cols-[minmax(0,9rem)_1fr_2.5rem] items-center gap-3 text-left text-[13px]">
                              <span className="truncate text-right text-ink-2" title={x.name}>{x.name}</span>
                              <span className="h-5 rounded-sm bg-line-2">
                                <span className={`block h-5 rounded-sm transition group-hover:opacity-80 ${active ? "ring-2 ring-accent-strong" : ""}`}
                                  style={{ width: `${(100 * x.count) / max}%`, background: `rgba(47,125,225,${Math.max(0.35, 1 - i * 0.13)})` }} />
                              </span>
                              <span className="tabular text-ink">{x.count}</span>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </Panel>

                <Panel title={<>{t("dx.alerts")} {!!alerts.length && <span className="ml-1 rounded-full bg-bad px-1.5 py-0.5 text-[11px] text-white">{alerts.length}</span>}</>} flush>
                  {!alerts.length ? <EmptyState>{t("dx.al.none")}</EmptyState> : (
                    <ul className="divide-y divide-line-2 px-3">
                      {(allAlerts ? alerts : alerts.slice(0, 5)).map((a) => (
                        <li key={a.title}>
                          <Link href={a.href} className="flex items-center gap-3 rounded-md px-2 py-2.5 hover:bg-line-2">
                            <span className={`grid size-9 shrink-0 place-items-center rounded-lg ${TILE[a.tone]}`}><Icon name={a.icon} size={18} /></span>
                            <span className="min-w-0 flex-1">
                              <span className="block truncate text-[13px] font-medium text-ink">{a.title}</span>
                              <span className="block truncate text-[12px] text-ink-3">{a.sub}</span>
                            </span>
                            <Icon name="back" size={14} className="rotate-180 text-ink-3" />
                          </Link>
                        </li>
                      ))}
                      {alerts.length > 5 && <li><button type="button" onClick={() => setAllAlerts(!allAlerts)}
                        className="w-full px-2 py-2 text-left text-[13px] font-medium text-accent hover:underline">
                        {allAlerts ? t("dx.al.less") : t("dx.al.more", { n: alerts.length - 5 })}</button></li>}
                    </ul>
                  )}
                </Panel>
              </div>

              <div className="grid gap-4 xl:grid-cols-5">
                <Panel title={t("dx.ch.upcoming")} action={viewAll("/gages")} flush className="xl:col-span-3">
                  {!d.gages.upcoming.length ? <EmptyState>—</EmptyState> : (
                    <div className="overflow-x-auto px-3"><table className="data-table">
                      <thead><tr><th>{t("dx.col.id")}</th><th>{t("dx.col.description")}</th><th>{t("dx.col.next")}</th><th className="text-right">{t("dx.col.days")}</th><th>{t("dx.status")}</th></tr></thead>
                      <tbody>{d.gages.upcoming.map((g) => {
                        const days = g.next_due_date ? daysBetween(d.as_of, g.next_due_date) : null;
                        return (
                          <tr key={g.id}>
                            <td><Link href={`/gages/${g.id}`} className="font-mono text-[12px] text-accent hover:underline">{g.gage_code}</Link></td>
                            <td className="max-w-[240px] truncate text-[12.5px]">{g.description}</td>
                            <td className="tabular text-[12.5px]">{fmtDate(g.next_due_date)}</td>
                            <td className={`tabular text-right text-[12.5px] font-semibold ${days === null ? "text-ink-3" : days < 0 ? "text-bad" : days <= 15 ? "text-warn" : "text-ok"}`}>{days ?? "—"}</td>
                            <td><ToneBadge tone={STATUS_TONE[g.status] as Tone}>{t(`status.${g.status}`)}</ToneBadge></td>
                          </tr>
                        );
                      })}</tbody></table></div>
                  )}
                </Panel>

                {can("lab:read") && <Panel title={t("dx.labRequests")} action={viewAll("/laboratory/requests")} flush className="xl:col-span-2">
                  {!recentRequests.length ? <EmptyState>{t("lab.request.empty")}</EmptyState> : (
                    <div className="overflow-x-auto px-3"><table className="data-table">
                      <thead><tr><th>{t("dx.col.folio")}</th><th>{t("dx.col.part")}</th><th>{t("dx.col.priority")}</th><th>{t("dx.status")}</th></tr></thead>
                      <tbody>{recentRequests.map((r) => (
                        <tr key={r.id}>
                          <td><Link href="/laboratory/requests" className="whitespace-nowrap font-mono text-[12px] text-accent hover:underline">{r.request_code}</Link></td>
                          <td className="font-mono text-[12px]">{r.part_number ?? "—"}</td>
                          <td><ToneBadge tone={PRIORITY_TONE[r.priority]}>{t(`lab.priority.${r.priority}`)}</ToneBadge></td>
                          <td><ToneBadge tone={REQ_STATUS_TONE[r.status]}>{t(`lab.rstatus.${r.status}`)}</ToneBadge></td>
                        </tr>
                      ))}</tbody></table></div>
                  )}
                </Panel>}
              </div>

              <div className="grid gap-4 xl:grid-cols-3">
                {can("audit:read") && <Panel title={t("dx.activity")} action={viewAll("/audit")} flush>
                  {!(activity.data?.items ?? []).length ? <EmptyState>{t("audit.empty")}</EmptyState> : (
                    <div className="overflow-x-auto px-3"><table className="data-table">
                      <thead><tr><th>{t("dx.col.date")}</th><th>{t("dx.col.user")}</th><th>{t("dx.col.action")}</th></tr></thead>
                      <tbody>{(activity.data?.items ?? []).map((e) => (
                        <tr key={e.id}>
                          <td className="whitespace-nowrap tabular text-[12px]">{fmtDateTime(e.created_at)}</td>
                          <td className="max-w-[130px] truncate text-[12px]">{e.actor_name ?? "—"}</td>
                          <td className="max-w-[150px] truncate font-mono text-[11.5px]" title={e.action}>{e.action}</td>
                        </tr>
                      ))}</tbody></table></div>
                  )}
                </Panel>}

                {d.calibration && <Panel title={t("dx.ch.calibrations")} action={viewAll("/calibrations")}>
                  <div className="mb-2 flex flex-wrap gap-1.5">
                    <ToneBadge tone="ok">Σ {d.calibration.released_in_period}</ToneBadge>
                    {Object.entries(d.calibration.results_in_period).map(([k, v]) => <ToneBadge key={k} tone="mute">{k}: {v}</ToneBadge>)}
                  </div>
                  <Columns lang={lang} months={months} series={[{ label: t("dx.ch.calibrations"), color: "#2f7de1", values: d.calibration.released_by_month.map((m) => m.count) }]} />
                </Panel>}

                <Panel title={t("dx.ch.compliance")}>
                  <ul className="space-y-3">
                    {d.gages.compliance_by_plant.map((p) => {
                      const v = p.pct_current ?? 0;
                      const color = v >= 90 ? "bg-ok" : v >= 75 ? "bg-[#e0a100]" : "bg-bad";
                      const id = plants.find((x) => x.code === p.plant)?.id ?? "";
                      return (
                        <li key={p.plant}>
                          <button type="button" disabled={!id} title={t("dx.clickFilter")}
                            onClick={() => applyNow({ plant_id: filters.plant_id === id ? "" : id, department_id: "" })}
                            className="group grid w-full grid-cols-[minmax(0,9rem)_1fr_3.5rem] items-center gap-3 text-left text-[13px]">
                            <span className="truncate text-ink-2" title={p.name}>{p.name}</span>
                            <span className="h-4 rounded-sm bg-line-2"><span className={`block h-4 rounded-sm ${color} group-hover:opacity-80`} style={{ width: `${v}%` }} /></span>
                            <span className="tabular text-right font-semibold text-ink">{p.pct_current ?? "—"}%</span>
                          </button>
                          <div className="text-[11px] text-ink-3">{t("dx.complianceSub", { a: p.current, b: p.active, c: p.overdue })}</div>
                        </li>
                      );
                    })}
                  </ul>
                </Panel>
              </div>
            </>
          )}

          <h2 className="pt-2 text-[12px] font-semibold uppercase tracking-[0.12em] text-ink-3">{t("dx.details")}</h2>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
            {secondary.map((x) => (
              <Link key={x.l} href={x.h} className="rounded-xl border border-line bg-surface px-3 py-2.5 hover:border-accent/40">
                <div className="truncate text-[11.5px] text-ink-3" title={x.l}>{x.l}</div>
                <div className="tabular text-xl font-semibold text-ink">{x.v}</div>
              </Link>
            ))}
          </div>

          <div className="grid items-start gap-4 lg:grid-cols-2">
            {d.laboratory && <Panel title={t("dx.ch.lab")}>
              <Columns lang={lang} months={months} series={[{ label: t("dx.ch.labReceived"), color: "#2f7de1", values: d.laboratory.requests_by_month.map((m) => m.count) },
                { label: t("dx.ch.labCompleted"), color: "#17a34a", values: d.laboratory.completed_by_month.map((m) => m.count) }]} />
            </Panel>}
            {d.oot && <Panel title={t("dx.ch.oot")}>
              <Columns lang={lang} months={months} series={[{ label: "OOT", color: "#c0262d", values: d.oot.detected_by_month.map((m) => m.count) }]} />
            </Panel>}
            {d.laboratory && <Panel title={t("dx.ch.workload")} flush>
              {!d.laboratory.workload.length ? <EmptyState>—</EmptyState> : (
                <div className="px-3"><table className="data-table"><thead><tr><th>{t("dx.col.technician")}</th><th>{t("dx.col.orders")}</th><th>{t("dx.col.hours")}</th></tr></thead>
                  <tbody>{d.laboratory.workload.map((w) => <tr key={w.technician}><td>{w.technician}</td><td className="tabular">{w.open_orders}</td>
                    <td className="tabular">{w.planned_hours}</td></tr>)}</tbody></table></div>
              )}
            </Panel>}
            {d.msa && <Panel title={t("dx.ch.msaMethod")} flush>
              {!Object.keys(d.msa.by_method).length ? <EmptyState>—</EmptyState> : (
                <div className="overflow-x-auto px-3"><table className="data-table"><thead><tr><th>{t("dx.col.method")}</th>
                  {DECISIONS.map((x) => <th key={x} className="text-[10px]">{x === "NOT_CALCULATED" ? "—" : t(`msa.dec.${x}`)}</th>)}</tr></thead>
                  <tbody>{Object.entries(d.msa.by_method).map(([m, v]) => <tr key={m}><td className="text-[12px]">{t(`msa.m.${m}` as "msa.m.BIAS")}</td>
                    {DECISIONS.map((x) => <td key={x} className="tabular">{v[x] ?? 0}</td>)}</tr>)}</tbody></table></div>
              )}
            </Panel>}
          </div>
          <p className="text-[11px] text-ink-3">{t("dx.reconcile")}{can("compliance:read") && <> · <Link className="text-accent hover:underline" href="/reports">{t("nav.reports")}</Link></>}</p>
        </div>
      )}
    </>
  );
}
