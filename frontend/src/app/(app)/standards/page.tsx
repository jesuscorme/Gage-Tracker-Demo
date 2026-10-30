"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Alert, Button, Card, EmptyState, ErrorState, Field, Input, Loading, Modal, PageHeader, Select, ToneBadge, errorText,
} from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { STANDARD_CATEGORIES, STD_STATUS_TONE } from "@/lib/status";
import type { Plant, Standard } from "@/lib/types";

export default function StandardsPage() {
  const { t, fmtDate } = useI18n();
  const { can } = useAuth();
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [creating, setCreating] = useState(false);
  const list = useResource(() => api.get<Standard[]>("/standards", { q, category }), [q, category]);

  return (
    <>
      <PageHeader title={t("std.title")}
        actions={can("standards:manage") && <Button variant="primary" onClick={() => setCreating(true)}>+ {t("std.new")}</Button>} />
      <Card flush>
        <div className="grid gap-2 border-b border-line p-3 sm:grid-cols-[2fr_1fr]">
          <Input type="search" placeholder={`${t("std.code")}, ${t("common.description").toLowerCase()}, S/N`} value={q} onChange={(e) => setQ(e.target.value)} />
          <Select value={category} onChange={(e) => setCategory(e.target.value)} aria-label={t("std.category")}>
            <option value="">{t("std.category")}: {t("common.all")}</option>
            {STANDARD_CATEGORIES.map((c) => <option key={c} value={c}>{t(`std.cat.${c}`)}</option>)}
          </Select>
        </div>
        {list.error ? <div className="px-4"><ErrorState error={list.error} onRetry={list.reload} /></div>
          : !list.data ? <div className="px-4"><Loading /></div>
          : list.data.length === 0 ? <EmptyState>{t("std.empty")}</EmptyState>
          : (
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead><tr><th>{t("std.code")}</th><th>{t("common.description")}</th><th className="hidden md:table-cell">{t("std.category")}</th>
                  <th className="hidden lg:table-cell">{t("gage.field.plant")}</th><th>{t("std.validUntil")}</th><th>{t("common.status")}</th></tr></thead>
                <tbody>
                  {list.data.map((s) => (
                    <tr key={s.id}>
                      <td><Link href={`/standards/${s.id}`} className="font-mono text-[13px] font-semibold text-accent hover:underline">{s.standard_code}</Link></td>
                      <td className="max-w-[300px]"><div className="truncate">{s.description}</div>
                        {s.serial_number && <div className="font-mono text-[11px] text-ink-3">S/N {s.serial_number}</div>}</td>
                      <td className="hidden text-[12px] md:table-cell">{t(`std.cat.${s.category as (typeof STANDARD_CATEGORIES)[number]}`)}{s.subtype && ` · ${s.subtype}`}</td>
                      <td className="hidden font-mono text-[12px] lg:table-cell">{s.plant.code}</td>
                      <td className="tabular">{fmtDate(s.valid_until)}
                        {s.days_to_expiry !== null && s.days_to_expiry < 0 && <div className="text-[11px] font-semibold text-bad">{t("gages.daysOverdue", { n: -s.days_to_expiry })}</div>}</td>
                      <td><ToneBadge tone={STD_STATUS_TONE[s.status]}>{t(`std.status.${s.status}`)}</ToneBadge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </Card>
      <CreateStandard open={creating} onClose={() => setCreating(false)} />
    </>
  );
}

function CreateStandard({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const router = useRouter();
  const plants = useResource(() => (open ? api.get<Plant[]>("/plants") : Promise.resolve([])), [open]);
  const empty = { standard_code: "", description: "", category: "GAUGE_BLOCK", subtype: "", plant_id: "", manufacturer: "",
    model: "", serial_number: "", range_min: "", range_max: "", unit: "", resolution: "", accuracy: "", location: "",
    calibration_frequency_days: "365" };
  const [f, setF] = useState(empty);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const s = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  useEffect(() => {
    const first = plants.data?.[0];
    if (first) setF((x) => (x.plant_id ? x : { ...x, plant_id: first.id }));
  }, [plants.data]);

  async function save() {
    setBusy(true);
    setError(null);
    const body: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(f)) if (v.trim()) body[k] = k === "calibration_frequency_days" ? Number(v) : v.trim();
    try {
      const created = await api.post<Standard>("/standards", body);
      router.push(`/standards/${created.id}`);
    } catch (err) {
      setError(errorText(t, err));
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={t("std.new")}
      footer={<><Button onClick={onClose}>{t("common.cancel")}</Button>
        <Button variant="primary" loading={busy} disabled={!f.standard_code || !f.description || !f.plant_id} onClick={save}>{t("common.create")}</Button></>}>
      {error && <Alert>{error}</Alert>}
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("std.code")} required><Input className="font-mono uppercase" value={f.standard_code} onChange={s("standard_code")} /></Field>
        <Field label={t("std.category")} required>
          <Select value={f.category} onChange={s("category")}>{STANDARD_CATEGORIES.map((c) => <option key={c} value={c}>{t(`std.cat.${c}`)}</option>)}</Select>
        </Field>
        <Field label={t("common.description")} required className="sm:col-span-2"><Input value={f.description} onChange={s("description")} /></Field>
        <Field label={t("std.subtype")}><Input value={f.subtype} onChange={s("subtype")} /></Field>
        <Field label={t("gage.field.plant")} required>
          <Select value={f.plant_id} onChange={s("plant_id")}>{plants.data?.map((p) => <option key={p.id} value={p.id}>{p.code} — {p.name}</option>)}</Select>
        </Field>
        <Field label={t("gage.field.manufacturer")}><Input value={f.manufacturer} onChange={s("manufacturer")} /></Field>
        <Field label={t("gage.field.model")}><Input value={f.model} onChange={s("model")} /></Field>
        <Field label={t("gage.field.serial")}><Input className="font-mono" value={f.serial_number} onChange={s("serial_number")} /></Field>
        <Field label={t("gage.field.location")}><Input value={f.location} onChange={s("location")} /></Field>
        <Field label={t("gage.field.rangeMin")}><Input inputMode="decimal" className="font-mono" value={f.range_min} onChange={s("range_min")} /></Field>
        <Field label={t("gage.field.rangeMax")}><Input inputMode="decimal" className="font-mono" value={f.range_max} onChange={s("range_max")} /></Field>
        <Field label={t("gage.field.unit")}><Input value={f.unit} onChange={s("unit")} /></Field>
        <Field label={t("gage.field.resolution")}><Input inputMode="decimal" className="font-mono" value={f.resolution} onChange={s("resolution")} /></Field>
        <Field label={t("gage.field.accuracy")}><Input value={f.accuracy} onChange={s("accuracy")} /></Field>
        <Field label={t("gage.field.frequency")} required><Input type="number" min={1} className="font-mono" value={f.calibration_frequency_days} onChange={s("calibration_frequency_days")} /></Field>
      </div>
    </Modal>
  );
}
