"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import {
  Alert, Button, Card, EmptyState, ErrorState, Field, Input, Loading, Modal, PageHeader, Select, Textarea, ToneBadge, errorText,
} from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { PRIORITY_TONE, REQ_STATUS_TONE } from "@/lib/status";
import type { Department, LabService, Plant, ServiceRequest } from "@/lib/types";

const STATUSES = ["SUBMITTED", "APPROVED", "REJECTED", "IN_PROGRESS", "COMPLETED", "CANCELLED"] as const;

export default function RequestsPage() {
  return <Suspense fallback={<Loading />}><Requests /></Suspense>;
}

function Requests() {
  const { t, fmtDate } = useI18n();
  const { can } = useAuth();
  const params = useSearchParams();
  const [status, setStatus] = useState(params.get("status") ?? "");
  const [q, setQ] = useState("");
  const [creating, setCreating] = useState(params.get("new") === "1");
  const list = useResource(() => api.get<ServiceRequest[]>("/lab/requests", { status: status ? [status] : undefined, q }), [status, q]);

  return (
    <>
      <PageHeader title={t("nav.labRequests")}
        actions={can("lab:request") && <Button variant="primary" onClick={() => setCreating(true)}>+ {t("lab.request.new")}</Button>} />
      <Card flush>
        <div className="grid gap-2 border-b border-line p-3 sm:grid-cols-[2fr_1fr]">
          <Input type="search" placeholder={`SR-…, ${t("common.part").toLowerCase()}`} value={q} onChange={(e) => setQ(e.target.value)} />
          <Select value={status} onChange={(e) => setStatus(e.target.value)} aria-label={t("common.status")}>
            <option value="">{t("common.status")}: {t("common.all")}</option>
            {STATUSES.map((s) => <option key={s} value={s}>{t(`lab.rstatus.${s}`)}</option>)}
          </Select>
        </div>
        {list.error ? <div className="px-4"><ErrorState error={list.error} onRetry={list.reload} /></div>
          : !list.data ? <div className="px-4"><Loading /></div>
          : list.data.length === 0 ? <EmptyState>{t("lab.request.empty")}</EmptyState>
          : (
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead><tr><th>{t("lab.request.code")}</th><th>{t("lab.request.service")}</th><th>{t("common.part")}</th>
                  <th className="hidden md:table-cell">{t("lab.request.requester")}</th><th>{t("common.priority")}</th>
                  <th>{t("lab.request.committed")}</th><th>{t("common.status")}</th></tr></thead>
                <tbody>
                  {list.data.map((r) => (
                    <tr key={r.id}>
                      <td><Link href={`/laboratory/requests/${r.id}`} className="font-mono text-[13px] font-semibold text-accent hover:underline">{r.request_code}</Link></td>
                      <td>{r.service_name}</td>
                      <td className="font-mono text-[12px]">{r.part_number ?? "—"}{r.part_revision && ` rev ${r.part_revision}`}</td>
                      <td className="hidden text-[12px] md:table-cell">{r.requester_name}</td>
                      <td><ToneBadge tone={PRIORITY_TONE[r.priority]}>{t(`lab.priority.${r.priority}`)}</ToneBadge></td>
                      <td className="tabular">{fmtDate(r.committed_date ?? r.requested_date)}</td>
                      <td><ToneBadge tone={REQ_STATUS_TONE[r.status]}>{t(`lab.rstatus.${r.status}`)}</ToneBadge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </Card>
      {creating && <NewRequest onClose={() => setCreating(false)} />}
    </>
  );
}

function NewRequest({ onClose }: { onClose: () => void }) {
  const { t } = useI18n();
  const router = useRouter();
  const plants = useResource(() => api.get<Plant[]>("/plants"));
  const depts = useResource(() => api.get<Department[]>("/departments"));
  const services = useResource(() => api.get<LabService[]>("/lab/services"));
  const [f, setF] = useState({ plant_id: "", department_id: "", service_id: "", customer_type: "INTERNAL", customer_name: "",
    part_number: "", part_revision: "", quantity: "1", description: "", priority: "NORMAL", requested_date: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const p = plants.data?.[0];
    if (p) setF((x) => (x.plant_id ? x : { ...x, plant_id: p.id }));
  }, [plants.data]);
  const s = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const r = await api.post<ServiceRequest>("/lab/requests", {
        ...f, department_id: f.department_id || null, customer_name: f.customer_name || null, part_number: f.part_number || null,
        part_revision: f.part_revision || null, quantity: Number(f.quantity || 1),
      });
      router.push(`/laboratory/requests/${r.id}`);
    } catch (err) {
      setError(errorText(t, err));
      setBusy(false);
    }
  }

  return (
    <Modal open title={t("lab.request.new")} onClose={onClose}
      footer={<><Button onClick={onClose}>{t("common.cancel")}</Button>
        <Button variant="primary" loading={busy} disabled={!f.service_id || !f.plant_id || f.description.length < 3 || !f.requested_date} onClick={save}>{t("common.create")}</Button></>}>
      {error && <Alert>{error}</Alert>}
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("lab.request.service")} required className="sm:col-span-2">
          <Select value={f.service_id} onChange={s("service_id")}><option value="" />{services.data?.map((x) => <option key={x.id} value={x.id}>{x.code} — {x.name}</option>)}</Select>
        </Field>
        <Field label={t("gage.field.plant")} required>
          <Select value={f.plant_id} onChange={s("plant_id")}>{plants.data?.map((p) => <option key={p.id} value={p.id}>{p.code} — {p.name}</option>)}</Select>
        </Field>
        <Field label={t("gage.field.department")}>
          <Select value={f.department_id} onChange={s("department_id")}><option value="">—</option>
            {depts.data?.filter((d) => d.plant_id === f.plant_id).map((d) => <option key={d.id} value={d.id}>{d.code} — {d.name}</option>)}</Select>
        </Field>
        <Field label={t("lab.request.customer")}>
          <Select value={f.customer_type} onChange={s("customer_type")}>
            <option value="INTERNAL">{t("lab.request.INTERNAL")}</option><option value="EXTERNAL">{t("lab.request.EXTERNAL")}</option>
          </Select>
        </Field>
        <Field label={t("common.name")}><Input value={f.customer_name} onChange={s("customer_name")} /></Field>
        <Field label={t("common.part")}><Input className="font-mono" value={f.part_number} onChange={s("part_number")} /></Field>
        <Field label={t("common.revision")}><Input className="font-mono" value={f.part_revision} onChange={s("part_revision")} /></Field>
        <Field label={t("lab.request.quantity")}><Input type="number" min={1} value={f.quantity} onChange={s("quantity")} /></Field>
        <Field label={t("common.priority")}>
          <Select value={f.priority} onChange={s("priority")}>{(["LOW", "NORMAL", "HIGH", "URGENT"] as const).map((p) => <option key={p} value={p}>{t(`lab.priority.${p}`)}</option>)}</Select>
        </Field>
        <Field label={t("lab.request.requested")} required><Input type="date" className="font-mono" value={f.requested_date} onChange={s("requested_date")} /></Field>
        <Field label={t("common.description")} required className="sm:col-span-2"><Textarea value={f.description} onChange={s("description")} /></Field>
      </div>
    </Modal>
  );
}
