"use client";

import Link from "next/link";
import { useState } from "react";
import { BarChart, LineChart } from "@/components/charts";
import { Button, Card, EmptyState, ErrorState, Field, Input, KpiTile, LinkButton, Loading, PageHeader, Select, ToneBadge, type Tone } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { usePlants, useUsers } from "@/lib/lookups";
import { GAGE_STATUSES, STATUS_TONE } from "@/lib/status";
import type { Department, GageStatus } from "@/lib/types";

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

export default function DashboardPage() {
  const { t, fmtDate } = useI18n();
  const { membership, can } = useAuth();
  const plants = usePlants();
  const users = useUsers();
  const types = useResource(() => api.get<{ id: string; code: string; name: string }[]>("/gage-types"));
  const [draft, setDraft] = useState<F>({});
  const [filters, setFilters] = useState<F>({});
  const depts = useResource(() => (draft.plant_id ? api.get<Department[]>("/departments", { plant_id: draft.plant_id }) : Promise.resolve([])), [draft.plant_id]);
  const data = useResource(() => api.get<Overview>("/dashboard/overview", filters), [JSON.stringify(filters)]);
  const set = (k: string, v: string) => setDraft({ ...draft, [k]: v });
  const d = data.data;
  const months = d?.period.months.map((m) => m.slice(2)) ?? [];
  const exp = d?.expirations ?? {};

  return (
    <>
      <PageHeader eyebrow={membership?.organization_name} title={t("dx.title")}>
        {d && <p className="mt-1 text-[12px] text-ink-3">{t("dx.asOf", { d: fmtDate(d.as_of), f: fmtDate(d.period.from), t: fmtDate(d.period.to) })}</p>}
      </PageHeader>

      <Card>
        <div className="grid gap-2 sm:grid-cols-4 lg:grid-cols-8 lg:items-end">
          <Field label={t("dx.plant")}><Select value={draft.plant_id ?? ""} onChange={(e) => setDraft({ ...draft, plant_id: e.target.value, department_id: "" })}>
            <option value="">{t("dx.all")}</option>{plants.map((p) => <option key={p.id} value={p.id}>{p.code}</option>)}</Select></Field>
          <Field label={t("dx.department")}><Select value={draft.department_id ?? ""} disabled={!draft.plant_id} onChange={(e) => set("department_id", e.target.value)}>
            <option value="">{t("dx.all")}</option>{(depts.data ?? []).map((x) => <option key={x.id} value={x.id}>{x.code}</option>)}</Select></Field>
          <Field label={t("dx.type")}><Select value={draft.gage_type_id ?? ""} onChange={(e) => set("gage_type_id", e.target.value)}>
            <option value="">{t("dx.all")}</option>{(types.data ?? []).map((x) => <option key={x.id} value={x.id}>{x.code}</option>)}</Select></Field>
          <Field label={t("dx.status")}><Select value={draft.status ?? ""} onChange={(e) => set("status", e.target.value)}>
            <option value="">{t("dx.all")}</option>{GAGE_STATUSES.map((s) => <option key={s} value={s}>{t(`status.${s}`)}</option>)}</Select></Field>
          <Field label={t("dx.responsible")}><Select value={draft.responsible_id ?? ""} onChange={(e) => set("responsible_id", e.target.value)}>
            <option value="">{t("dx.all")}</option>{users.list.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}</Select></Field>
          <Field label={t("dx.from")}><Input type="date" value={draft.date_from ?? ""} onChange={(e) => set("date_from", e.target.value)} /></Field>
          <Field label={t("dx.to")}><Input type="date" value={draft.date_to ?? ""} onChange={(e) => set("date_to", e.target.value)} /></Field>
          <div className="flex gap-2">
            <Button variant="primary" onClick={() => setFilters(Object.fromEntries(Object.entries(draft).filter(([, v]) => v)))}>{t("dx.apply")}</Button>
            <Button variant="ghost" onClick={() => { setDraft({}); setFilters({}); }}>{t("dx.reset")}</Button>
          </div>
        </div>
      </Card>

      {data.error ? <ErrorState error={data.error} onRetry={data.reload} /> : !d ? <Loading /> : (
        <div className="mt-4 space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
            <KpiTile label={t("dx.kpi.total")} value={d.gages.total} href="/gages" />
            <KpiTile label={t("dx.kpi.current")} value={d.gages.current} tone="ok" href="/gages?status=CALIBRATED" />
            <KpiTile label={t("dx.kpi.dueSoon")} value={d.gages.due_soon} tone="warn" href="/gages?status=DUE_SOON" />
            <KpiTile label={t("dx.kpi.overdue")} value={d.gages.overdue} tone="bad" href="/gages?status=OVERDUE" />
            <KpiTile label={t("dx.kpi.oos")} value={d.gages.out_of_service} tone="block" href="/gages?status=OUT_OF_SERVICE" />
            {d.calibration && <KpiTile label={t("dx.kpi.calPending")} value={d.calibration.pending} tone="info" href="/calibrations" />}
            {d.calibration && <KpiTile label={t("dx.kpi.calInProcess")} value={d.calibration.in_process} tone="info" href="/calibrations" />}
            {d.laboratory && <KpiTile label={t("dx.kpi.requests")} value={d.laboratory.requests_open} href="/laboratory/requests" />}
            {d.laboratory && <KpiTile label={t("dx.kpi.woOpen")} value={d.laboratory.work_orders_open} href="/laboratory/work-orders" />}
            {d.laboratory && <KpiTile label={t("dx.kpi.woOverdue")} value={d.laboratory.work_orders_overdue} tone="bad" href="/laboratory/work-orders" />}
            {d.msa && <KpiTile label={t("dx.kpi.msaOpen")} value={d.msa.open} href="/msa" />}
            {d.msa && <KpiTile label={t("dx.kpi.msaDone")} value={d.msa.completed} tone="ok" href="/msa" />}
            {d.msa && <KpiTile label={t("dx.kpi.msaNok")} value={d.msa.not_acceptable} tone="bad" href="/msa" />}
            {d.oot && <KpiTile label={t("dx.kpi.ootOpen")} value={d.oot.open} tone="bad" href="/oot" sub={d.oot.gages_restricted ? `${d.oot.gages_restricted} ⛔` : undefined} />}
            {exp.standards_expiring !== undefined && <KpiTile label={t("dx.kpi.stdExpiring")} value={exp.standards_expiring} tone="warn" href="/standards" />}
            {exp.authorizations_expiring !== undefined && <KpiTile label={t("dx.kpi.compExpiring")}
              value={(exp.authorizations_expiring ?? 0) + (exp.competency_records_expiring ?? 0)} tone="warn" href="/competency" />}
          </div>

          {d.gages.total === 0 ? <Card><EmptyState action={!Object.keys(filters).length && can("gages:create") &&
            <LinkButton href="/gages/new" variant="primary">+ {t("gages.new")}</LinkButton>}>
            {Object.keys(filters).length ? t("dx.noData") : t("dashboard.empty")}</EmptyState></Card> : (
            <div className="grid gap-4 lg:grid-cols-2">
              <Card title={t("dx.ch.status")}>
                <BarChart title="" labels={GAGE_STATUSES.map((s) => t(`status.${s}`))} values={GAGE_STATUSES.map((s) => d.gages.by_status[s] ?? 0)} />
                <div className="mt-1 flex flex-wrap gap-1.5">{GAGE_STATUSES.map((s) => <ToneBadge key={s} tone={STATUS_TONE[s] as Tone}>{t(`status.${s}`)}: {d.gages.by_status[s] ?? 0}</ToneBadge>)}</div>
              </Card>
              <Card title={t("dx.ch.type")}><BarChart title="" labels={d.gages.by_type.map((x) => x.type)} values={d.gages.by_type.map((x) => x.count)} /></Card>
              {d.calibration && <Card title={t("dx.ch.calibrations")}>
                <LineChart title="" series={[{ label: t("dx.ch.calibrations"), values: d.calibration.released_by_month.map((m) => m.count) }]} xLabels={months} height={170} />
                <p className="text-[12px] text-ink-3">Σ {d.calibration.released_in_period} · {Object.entries(d.calibration.results_in_period).map(([k, v]) => `${k}: ${v}`).join(" · ")}</p>
              </Card>}
              <Card title={t("dx.ch.upcoming")} flush>
                {!d.gages.upcoming.length ? <EmptyState>—</EmptyState> : (
                  <table className="data-table"><tbody>{d.gages.upcoming.map((g) => (
                    <tr key={g.id}><td><Link href={`/gages/${g.id}`} className="font-mono text-[12px] text-accent hover:underline">{g.gage_code}</Link></td>
                      <td className="max-w-[220px] truncate text-[12px]">{g.description}</td><td className="tabular text-[12px]">{fmtDate(g.next_due_date)}</td>
                      <td><ToneBadge tone={STATUS_TONE[g.status] as Tone}>{t(`status.${g.status}`)}</ToneBadge></td></tr>))}</tbody></table>
                )}
              </Card>
              <Card title={t("dx.ch.compliance")} flush>
                <table className="data-table"><thead><tr><th>{t("dx.col.plant")}</th><th>{t("dx.col.active")}</th><th>{t("dx.col.current")}</th>
                  <th>{t("dx.col.overdue")}</th><th>{t("dx.col.pct")}</th></tr></thead>
                  <tbody>{d.gages.compliance_by_plant.map((p) => <tr key={p.plant}><td className="font-mono text-[12px]">{p.plant}</td>
                    <td className="tabular">{p.active}</td><td className="tabular">{p.current}</td><td className="tabular">{p.overdue}</td>
                    <td><div className="flex items-center gap-2"><div className="h-2 w-24 rounded bg-line-2"><div className="h-2 rounded bg-ok" style={{ width: `${p.pct_current ?? 0}%` }} /></div>
                      <span className="tabular text-[12px]">{p.pct_current ?? "—"} %</span></div></td></tr>)}</tbody></table>
              </Card>
              {d.oot && <Card title={t("dx.ch.oot")}><LineChart title="" series={[{ label: "OOT", values: d.oot.detected_by_month.map((m) => m.count) }]} xLabels={months} height={170} /></Card>}
            </div>
          )}

          <div className="grid gap-4 lg:grid-cols-2">
            {d.laboratory && <Card title={t("dx.ch.lab")}>
              <LineChart title="" series={[{ label: t("dx.ch.labReceived"), values: d.laboratory.requests_by_month.map((m) => m.count) },
                { label: t("dx.ch.labCompleted"), values: d.laboratory.completed_by_month.map((m) => m.count) }]} xLabels={months} height={170} />
            </Card>}
            {d.laboratory && <Card title={t("dx.ch.workload")} flush>
              {!d.laboratory.workload.length ? <EmptyState>—</EmptyState> : (
                <table className="data-table"><thead><tr><th>{t("dx.col.technician")}</th><th>{t("dx.col.orders")}</th><th>{t("dx.col.hours")}</th></tr></thead>
                  <tbody>{d.laboratory.workload.map((w) => <tr key={w.technician}><td>{w.technician}</td><td className="tabular">{w.open_orders}</td>
                    <td className="tabular">{w.planned_hours}</td></tr>)}</tbody></table>
              )}
            </Card>}
            {d.msa && <Card title={t("dx.ch.msaStatus")}>
              {Object.keys(d.msa.by_status).length ? <BarChart title="" labels={Object.keys(d.msa.by_status)} values={Object.values(d.msa.by_status)} />
                : <EmptyState>—</EmptyState>}
            </Card>}
            {d.msa && <Card title={t("dx.ch.msaMethod")} flush>
              {!Object.keys(d.msa.by_method).length ? <EmptyState>—</EmptyState> : (
                <div className="overflow-x-auto"><table className="data-table"><thead><tr><th>{t("dx.col.method")}</th>
                  {DECISIONS.map((x) => <th key={x} className="text-[10px]">{x === "NOT_CALCULATED" ? "—" : t(`msa.dec.${x}`)}</th>)}</tr></thead>
                  <tbody>{Object.entries(d.msa.by_method).map(([m, v]) => <tr key={m}><td className="text-[12px]">{t(`msa.m.${m}` as "msa.m.BIAS")}</td>
                    {DECISIONS.map((x) => <td key={x} className="tabular">{v[x] ?? 0}</td>)}</tr>)}</tbody></table></div>
              )}
            </Card>}
          </div>
          <p className="text-[11px] text-ink-3">{t("dx.reconcile")}{can("compliance:read") && <> · <Link className="text-accent hover:underline" href="/reports">{t("nav.reports")}</Link></>}</p>
        </div>
      )}
    </>
  );
}
