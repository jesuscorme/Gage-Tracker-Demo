"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { DocumentsPanel } from "@/components/documents";
import { Icon } from "@/components/icons";
import {
  Alert, Button, Card, ErrorState, Field, Input, Loading, Modal, PageHeader, ReasonDialog, Select, Spec, StatusBadge,
  Textarea, ToneBadge, errorText, useAction,
} from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import type { MessageKey } from "@/lib/messages";
import { WO_STATUS_TONE } from "@/lib/status";
import type { Gage, InspectionResult, Page, WorkOrderDetail } from "@/lib/types";

const toLocal = (iso: string | null) => {
  if (!iso) return "";
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};

export default function WorkOrderPage() {
  const { id } = useParams<{ id: string }>();
  const { t, fmtDate, fmtDateTime } = useI18n();
  const { can, me } = useAuth();
  const wo = useResource(() => api.get<WorkOrderDetail>(`/lab/work-orders/${id}`), [id]);
  const [scheduling, setScheduling] = useState(false);
  const [dialog, setDialog] = useState<null | "cancel" | "complete" | "report">(null);
  const { busy, error, run } = useAction();
  if (wo.error) return <ErrorState error={wo.error} onRetry={wo.reload} />;
  if (!wo.data) return <Loading />;
  const w = wo.data;
  const mine = w.technician_id === me?.id;
  const current = w.results.filter((r) => !r.superseded);
  const issued = w.reports.find((r) => r.status === "ISSUED");

  return (
    <>
      <Link href="/laboratory/work-orders" className="mb-3 inline-flex items-center gap-1 text-[12px] text-ink-3 hover:text-ink"><Icon name="back" size={14} /> {t("nav.labWorkOrders")}</Link>
      <PageHeader eyebrow={w.service_name}
        title={<span className="flex flex-wrap items-center gap-3"><span className="font-mono">{w.work_order_code}</span>
          <ToneBadge tone={WO_STATUS_TONE[w.status]}>{t(`lab.wostatus.${w.status}`)}</ToneBadge>
          {w.overdue && <ToneBadge tone="bad">{t("lab.wo.overdue")}</ToneBadge>}</span>}
        actions={
          <>
            {can("lab:manage") && ["PENDING", "SCHEDULED"].includes(w.status) && (
              <Button variant={w.status === "PENDING" ? "primary" : "secondary"} onClick={() => setScheduling(true)}>
                {w.status === "PENDING" ? t("lab.wo.schedule") : t("lab.wo.reschedule")}
              </Button>
            )}
            {w.status === "SCHEDULED" && mine && can("lab:execute") && (
              <Button variant="primary" loading={busy === "start"} onClick={() => run("start", () => api.post(`/lab/work-orders/${w.id}/start`), wo.reload)}>{t("lab.wo.begin")}</Button>
            )}
            {w.status === "IN_PROGRESS" && (mine || can("lab:manage")) && can("lab:execute") && (
              <Button variant="primary" onClick={() => setDialog("complete")}>{t("lab.wo.complete")}</Button>
            )}
            {w.status === "COMPLETED" && can("lab:report") && (
              <Button variant="primary" onClick={() => setDialog("report")}>{issued ? t("lab.wo.reissue") : t("lab.wo.issueReport")}</Button>
            )}
            {can("lab:manage") && !["COMPLETED", "CANCELLED"].includes(w.status) && (
              <Button variant="danger" onClick={() => setDialog("cancel")}>{t("lab.wo.cancel")}</Button>
            )}
          </>
        }>
        <p className="mt-1 text-[13px] text-ink-2">
          <Link href={`/laboratory/requests/${w.service_request_id}`} className="font-mono text-accent hover:underline">{w.request_code}</Link>
          {" · "}{w.request.description}
        </p>
      </PageHeader>
      {error && <div className="mb-4"><Alert>{error}</Alert></div>}

      <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
        <div className="min-w-0 space-y-4">
          <Card title={t("common.general")}>
            <dl className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <Spec label={t("lab.wo.technician")}>{w.technician_name}</Spec>
              <Spec label={t("lab.wo.start")} mono>{w.scheduled_start ? fmtDateTime(w.scheduled_start) : null}</Spec>
              <Spec label={t("lab.wo.end")} mono>{w.scheduled_end ? fmtDateTime(w.scheduled_end) : null}</Spec>
              <Spec label={t("lab.request.committed")} mono>{fmtDate(w.due_date)}</Spec>
              <Spec label={t("lab.wo.plannedHours")} mono>{w.planned_hours}</Spec>
              <Spec label={t("common.part")} mono>{w.request.part_number ? `${w.request.part_number} rev ${w.request.part_revision ?? "—"}` : null}</Spec>
              <Spec label={t("lab.request.quantity")} mono>{String(w.request.quantity)}</Spec>
              <Spec label={t("lab.services.activity")}>{t(`comp.act.${w.required_activity}` as MessageKey)}</Spec>
            </dl>
            {w.observations && <p className="mt-3 whitespace-pre-wrap border-t border-line pt-3 text-[13px] text-ink-2">{w.observations}</p>}
          </Card>

          <Card flush title={t("lab.wo.equipment")}>
            {w.equipment.length === 0 ? <p className="px-4 py-4 text-[13px] text-ink-3">{t("common.none2")}</p> : (
              <ul className="divide-y divide-line-2">
                {w.equipment.map((g) => (
                  <li key={g.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
                    <Link href={`/gages/${g.id}`} className="font-mono text-[13px] font-semibold text-accent hover:underline">{g.gage_code}</Link>
                    <span className="flex-1 truncate text-[12px] text-ink-2">{g.description}</span>
                    <span className="text-[12px] text-ink-3">{t("gage.field.nextDue")}: {fmtDate(g.next_due_date)}</span>
                    <StatusBadge status={g.status} />
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card flush title={t("lab.dim.title")}>
            <ResultsTable results={w.results} />
            {w.status === "IN_PROGRESS" && can("lab:execute") && <ResultForm wo={w} onDone={wo.reload} />}
          </Card>

          <Card flush title={t("nav.labReports")}>
            {w.reports.length === 0 ? <p className="px-4 py-4 text-[13px] text-ink-3">{t("lab.report.empty")}</p> : (
              <ul className="divide-y divide-line-2">
                {w.reports.map((r) => (
                  <li key={r.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
                    <Link href={`/laboratory/reports/${r.id}`} className="font-mono text-[13px] font-semibold text-accent hover:underline">{r.report_code} rev {r.revision}</Link>
                    <ToneBadge tone={r.acceptance === "ACCEPTED" ? "ok" : "bad"}>{t(`lab.report.${r.acceptance}`)}</ToneBadge>
                    {r.status === "SUPERSEDED" && <ToneBadge tone="mute">{t("lab.report.superseded")}</ToneBadge>}
                    <span className="text-[12px] text-ink-3">{fmtDateTime(r.issued_at)}</span>
                    <Button variant="ghost" className="ml-auto h-7 px-2" onClick={() => api.download(`/attachments/${r.attachment_id}/download`, undefined, { open: true })}>PDF</Button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <DocumentsPanel entityType="work_order" entityId={w.id} title={t("doc.EVIDENCE")} canUpload={can("lab:execute") && w.status !== "CANCELLED"} />
        </div>

        <Card flush title={t("common.history")}>
          <ol className="px-4 py-3">
            {w.events.map((e, i) => (
              <li key={i} className="border-l-2 border-line pb-3 pl-3 last:pb-0">
                <div className="text-[12px] font-medium">{e.from_status ? `${t(`lab.wostatus.${e.from_status}` as MessageKey)} → ` : ""}{t(`lab.wostatus.${e.to_status}` as MessageKey)}</div>
                {e.comment && <p className="text-[12px] text-ink-2">“{e.comment}”</p>}
                <p className="text-[11px] text-ink-3">{e.changed_by_name} · {fmtDateTime(e.changed_at)}</p>
              </li>
            ))}
          </ol>
        </Card>
      </div>

      {scheduling && <ScheduleDialog wo={w} onClose={() => setScheduling(false)} onDone={() => { setScheduling(false); wo.reload(); }} />}
      <ReasonDialog open={dialog === "cancel"} title={t("lab.wo.cancel")} label={t("common.reasonRequired")} danger
        onClose={() => setDialog(null)} onConfirm={(reason) => api.post(`/lab/work-orders/${w.id}/cancel`, { reason }).then(wo.reload)} />
      <ReasonDialog open={dialog === "complete"} title={t("lab.wo.complete")} label={t("common.notes")} required={false}
        onClose={() => setDialog(null)} onConfirm={(o) => api.post(`/lab/work-orders/${w.id}/complete`, { observations: o || null }).then(wo.reload)}>
        <p className="text-[13px] text-ink-2">{current.length} · {current.filter((r) => r.result === "NOK").length} NOK</p>
      </ReasonDialog>
      <ReasonDialog open={dialog === "report"} title={issued ? t("lab.wo.reissue") : t("lab.wo.issueReport")}
        label={issued ? t("lab.report.revisionReason") : t("common.notes")} required={!!issued}
        onClose={() => setDialog(null)}
        onConfirm={(text) => api.post(`/lab/work-orders/${w.id}/reports`, issued ? { revision_reason: text } : { observations: text || null }).then(wo.reload)} />
    </>
  );
}

function ResultsTable({ results }: { results: InspectionResult[] }) {
  const { t } = useI18n();
  if (!results.length) return <p className="px-4 py-4 text-[13px] text-ink-3">{t("lab.dim.empty")}</p>;
  return (
    <div className="overflow-x-auto">
      <table className="data-table">
        <thead><tr><th>{t("common.part")}</th><th>{t("lab.dim.sample")}</th><th>{t("lab.dim.number")}</th><th>{t("lab.dim.characteristic")}</th>
          <th>{t("cal.point.nominal")}</th><th>LSL</th><th>USL</th><th>{t("cal.point.measured")}</th><th>Gage</th><th>{t("common.result")}</th></tr></thead>
        <tbody>
          {results.map((r) => (
            <tr key={r.id} className={r.superseded ? "text-ink-3 line-through" : ""}>
              <td className="font-mono text-[12px]">{r.part_number}{r.drawing_revision && <span className="text-ink-3"> /{r.drawing_revision}</span>}</td>
              <td className="font-mono text-[12px]">{r.sample_id ?? "—"}</td>
              <td className="font-mono">{r.characteristic_number}</td>
              <td className="max-w-[180px] truncate">{r.characteristic}{r.correction_reason && <div className="text-[11px] text-ink-3">↺ {r.correction_reason}</div>}</td>
              <td className="font-mono tabular">{r.nominal}</td>
              <td className="font-mono tabular">{r.lower_limit}</td>
              <td className="font-mono tabular">{r.upper_limit}</td>
              <td className="font-mono tabular font-semibold">{r.measured} {r.unit}</td>
              <td className="font-mono text-[12px]">{r.gage_code}</td>
              <td>{r.superseded ? "—" : <ToneBadge tone={r.result === "OK" ? "ok" : "bad"}>{r.result}</ToneBadge>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ResultForm({ wo, onDone }: { wo: WorkOrderDetail; onDone: () => void }) {
  const { t } = useI18n();
  const { busy, error, run } = useAction();
  const base = { part_number: wo.request.part_number ?? "", drawing_revision: wo.request.part_revision ?? "", sample_id: "1",
    characteristic_number: "", characteristic: "", nominal: "", lower_limit: "", upper_limit: "", measured: "", unit: "mm",
    gage_id: wo.equipment[0]?.id ?? "", supersedes_id: "", correction_reason: "" };
  const [f, setF] = useState(base);
  const s = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  const current = wo.results.filter((r) => !r.superseded);
  const ready = f.part_number && f.characteristic_number && f.characteristic && f.nominal && f.lower_limit && f.upper_limit && f.measured && f.gage_id
    && (!f.supersedes_id || f.correction_reason.length >= 3);
  return (
    <div className="border-t border-line bg-line-2/40 px-4 py-3">
      {error && <div className="mb-2"><Alert>{error}</Alert></div>}
      <div className="grid grid-cols-2 gap-2 md:grid-cols-6">
        <Input placeholder={t("common.part")} className="font-mono" value={f.part_number} onChange={s("part_number")} />
        <Input placeholder={t("lab.dim.drawingRev")} className="font-mono" value={f.drawing_revision} onChange={s("drawing_revision")} />
        <Input placeholder={t("lab.dim.sample")} className="font-mono" value={f.sample_id} onChange={s("sample_id")} />
        <Input placeholder={t("lab.dim.number")} className="font-mono" value={f.characteristic_number} onChange={s("characteristic_number")} />
        <Input placeholder={t("lab.dim.characteristic")} className="md:col-span-2" value={f.characteristic} onChange={s("characteristic")} />
        <Input placeholder={t("cal.point.nominal")} inputMode="decimal" className="font-mono" value={f.nominal} onChange={s("nominal")} />
        <Input placeholder="LSL" inputMode="decimal" className="font-mono" value={f.lower_limit} onChange={s("lower_limit")} />
        <Input placeholder="USL" inputMode="decimal" className="font-mono" value={f.upper_limit} onChange={s("upper_limit")} />
        <Input placeholder={t("cal.point.measured")} inputMode="decimal" className="font-mono" value={f.measured} onChange={s("measured")} />
        <Input placeholder={t("gage.field.unit")} value={f.unit} onChange={s("unit")} />
        <Select value={f.gage_id} onChange={s("gage_id")} aria-label="Gage">
          {wo.equipment.map((g) => <option key={g.id} value={g.id}>{g.gage_code}</option>)}
        </Select>
        <Select className="md:col-span-2" value={f.supersedes_id} onChange={s("supersedes_id")} aria-label={t("cal.point.correction")}>
          <option value="">{t("lab.dim.add")}</option>
          {current.map((r) => <option key={r.id} value={r.id}>{t("cal.point.correct")} #{r.characteristic_number} ({r.sample_id ?? "-"}) = {r.measured}</option>)}
        </Select>
        {f.supersedes_id && <Input className="md:col-span-3" placeholder={t("common.reasonRequired")} value={f.correction_reason} onChange={s("correction_reason")} />}
        <Button variant="primary" className={f.supersedes_id ? "" : "md:col-start-6"} disabled={!ready} loading={busy === "r"}
          onClick={() => run("r", () => api.post(`/lab/work-orders/${wo.id}/results`, {
            ...f, drawing_revision: f.drawing_revision || null, sample_id: f.sample_id || null,
            supersedes_id: f.supersedes_id || null, correction_reason: f.correction_reason || null,
          }), () => { setF({ ...f, characteristic_number: "", characteristic: "", nominal: "", lower_limit: "", upper_limit: "", measured: "", supersedes_id: "", correction_reason: "" }); onDone(); })}>
          {t("lab.dim.add")}
        </Button>
      </div>
    </div>
  );
}

function ScheduleDialog({ wo, onClose, onDone }: { wo: WorkOrderDetail; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const techs = useResource(() => api.get<{ id: string; full_name: string }[]>("/competency/authorized-users", { activity: wo.required_activity, plant_id: wo.plant_id }));
  const gages = useResource(() => api.get<Page<Gage>>("/gages", { available: true, page_size: 200, plant_id: wo.plant_id }));
  const [f, setF] = useState({ technician_id: wo.technician_id ?? "", start: toLocal(wo.scheduled_start), end: toLocal(wo.scheduled_end), reason: "" });
  const [selected, setSelected] = useState<string[]>(wo.equipment.map((g) => g.id));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!f.end && f.start) {
      const end = new Date(new Date(f.start).getTime() + Number(wo.planned_hours) * 3600_000);
      setF((x) => ({ ...x, end: toLocal(end.toISOString()) }));
    }
  }, [f.start, f.end, wo.planned_hours]);
  async function save() {
    setBusy(true);
    setError(null);
    try {
      await api.post(`/lab/work-orders/${wo.id}/schedule`, {
        technician_id: f.technician_id, scheduled_start: new Date(f.start).toISOString(), scheduled_end: new Date(f.end).toISOString(),
        gage_ids: selected, reason: f.reason || null,
      });
      onDone();
    } catch (err) {
      setError(errorText(t, err));
      setBusy(false);
    }
  }
  return (
    <Modal open title={`${wo.status === "PENDING" ? t("lab.wo.schedule") : t("lab.wo.reschedule")} · ${wo.work_order_code}`} onClose={onClose}
      footer={<><Button onClick={onClose}>{t("common.cancel")}</Button>
        <Button variant="primary" loading={busy} disabled={!f.technician_id || !f.start || !f.end || (wo.status === "SCHEDULED" && f.reason.length < 3)} onClick={save}>{t("common.save")}</Button></>}>
      {error && <Alert>{error}</Alert>}
      <Field label={t("lab.wo.technician")} required>
        <Select value={f.technician_id} onChange={(e) => setF({ ...f, technician_id: e.target.value })}>
          <option value="" />{techs.data?.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
        </Select>
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("lab.wo.start")} required><Input type="datetime-local" className="font-mono" value={f.start} onChange={(e) => setF({ ...f, start: e.target.value })} /></Field>
        <Field label={t("lab.wo.end")} required><Input type="datetime-local" className="font-mono" value={f.end} onChange={(e) => setF({ ...f, end: e.target.value })} /></Field>
      </div>
      <fieldset>
        <legend className="mb-1 text-[12px] font-medium text-ink-2">{t("lab.wo.equipment")}</legend>
        <div className="max-h-44 space-y-1 overflow-y-auto rounded border border-line p-2">
          {gages.data?.items.map((g) => (
            <label key={g.id} className="flex items-center gap-2 text-[13px]">
              <input type="checkbox" checked={selected.includes(g.id)} onChange={(e) => setSelected(e.target.checked ? [...selected, g.id] : selected.filter((x) => x !== g.id))} />
              <span className="font-mono">{g.gage_code}</span><span className="truncate text-ink-2">{g.description}</span>
            </label>
          ))}
        </div>
      </fieldset>
      {wo.status === "SCHEDULED" && (
        <Field label={t("lab.wo.rescheduleReason")} required><Textarea value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} /></Field>
      )}
    </Modal>
  );
}
