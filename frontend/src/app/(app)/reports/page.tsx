"use client";

import { useState } from "react";
import { Alert, Button, Card, EmptyState, Field, Input, Loading, PageHeader, Select, useAction } from "@/components/ui";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { useGages, usePlants } from "@/lib/lookups";

interface ReportDef { key: string; group: string; title: string; needs_gage: boolean; uses_period: boolean;
  columns: { key: string; label: string }[] }
interface ReportData { code: string; title: string; generated_at: string; columns: { key: string; label: string }[];
  rows: Record<string, unknown>[]; count: number }

const PREVIEW = 200;
const GROUPS = ["METROLOGY", "MSA", "LAB", "OOT"] as const;

export default function ReportsPage() {
  const { t, lang } = useI18n();
  const plants = usePlants();
  const gages = useGages();
  const cat = useResource(() => api.get<ReportDef[]>("/reports", { lang }), [lang]);
  const [key, setKey] = useState<string>("");
  const [f, setF] = useState<Record<string, string>>({});
  const [data, setData] = useState<ReportData | null>(null);
  const { busy, error, run } = useAction();
  const def = cat.data?.find((r) => r.key === key);
  const query = () => ({ lang, ...Object.fromEntries(Object.entries(f).filter(([, v]) => v)) });
  const show = (v: unknown) => (v === null || v === undefined ? "" : typeof v === "boolean" ? (v ? t("common.yes") : t("common.no"))
    : String(v).length >= 19 && String(v)[10] === "T" ? String(v).slice(0, 16).replace("T", " ") : String(v));

  return (
    <>
      <PageHeader title={t("rp.title")} />
      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <Card title={t("rp.select")} flush>
          {!cat.data ? <Loading /> : GROUPS.map((g) => {
            const items = cat.data!.filter((r) => r.group === g);
            if (!items.length) return null;
            return (
              <div key={g} className="border-b border-line px-3 py-2">
                <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-3">{t(`rp.group.${g}`)}</div>
                {items.map((r) => (
                  <button key={r.key} onClick={() => { setKey(r.key); setData(null); }}
                    className={`block w-full rounded px-2 py-1 text-left text-[13px] hover:bg-line-2 ${r.key === key ? "bg-accent/10 font-semibold text-accent" : ""}`}>
                    {r.title}
                  </button>
                ))}
                {g === "MSA" && <p className="px-2 pt-1 text-[11px] text-ink-3">{t("rp.msaNote")}</p>}
              </div>
            );
          })}
        </Card>
        <div className="space-y-4">
          {!def ? <Card><EmptyState>{t("rp.select")}</EmptyState></Card> : (
            <Card title={def.title}>
              {error && <Alert>{error}</Alert>}
              <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6 lg:items-end">
                <Field label={t("dx.plant")}><Select value={f.plant_id ?? ""} onChange={(e) => setF({ ...f, plant_id: e.target.value })}>
                  <option value="">{t("dx.all")}</option>{plants.map((p) => <option key={p.id} value={p.id}>{p.code}</option>)}</Select></Field>
                {def.uses_period && <>
                  <Field label={t("dx.from")}><Input type="date" value={f.date_from ?? ""} onChange={(e) => setF({ ...f, date_from: e.target.value })} /></Field>
                  <Field label={t("dx.to")}><Input type="date" value={f.date_to ?? ""} onChange={(e) => setF({ ...f, date_to: e.target.value })} /></Field>
                </>}
                {(def.needs_gage || ["calibrations_performed", "as_found_as_left", "lab_inspections"].includes(def.key)) && (
                  <Field label={t("rp.gage")} required={def.needs_gage}><Select value={f.gage_id ?? ""} onChange={(e) => setF({ ...f, gage_id: e.target.value })}>
                    <option value="">—</option>{gages.map((g) => <option key={g.id} value={g.id}>{g.gage_code}</option>)}</Select></Field>
                )}
                <Field label={t("rp.statusFilter")}><Input value={f.status ?? ""} onChange={(e) => setF({ ...f, status: e.target.value.toUpperCase() })} /></Field>
                <Button variant="primary" disabled={!!busy || (def.needs_gage && !f.gage_id)}
                  onClick={() => run("g", async () => setData(await api.get<ReportData>(`/reports/${def.key}`, query())))}>{t("rp.generate")}</Button>
              </div>
              {data && (
                <div className="mt-4">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="font-mono text-[12px] text-ink-3">{data.code}</span>
                    <span className="text-[13px] font-semibold">{t("rp.rows", { n: data.count })}</span>
                    <div className="ml-auto flex gap-2">
                      {(["pdf", "xlsx", "csv"] as const).map((fmt) => (
                        <Button key={fmt} onClick={() => run(fmt, () => api.download(`/reports/${def.key}`, { ...query(), format: fmt }))}>
                          {fmt.toUpperCase()}
                        </Button>
                      ))}
                    </div>
                  </div>
                  {data.count > PREVIEW && <p className="mb-2 text-[12px] text-ink-3">{t("rp.previewLimit", { n: PREVIEW })}</p>}
                  {!data.rows.length ? <EmptyState>—</EmptyState> : (
                    <div className="max-h-[60vh] overflow-auto rounded border border-line">
                      <table className="data-table"><thead className="sticky top-0 bg-surface"><tr>{data.columns.map((c) => <th key={c.key}>{c.label}</th>)}</tr></thead>
                        <tbody>{data.rows.slice(0, PREVIEW).map((r, i) => <tr key={i}>{data.columns.map((c) =>
                          <td key={c.key} className="max-w-[260px] truncate text-[12px]">{show(r[c.key])}</td>)}</tr>)}</tbody></table>
                    </div>
                  )}
                </div>
              )}
            </Card>
          )}
        </div>
      </div>
    </>
  );
}
