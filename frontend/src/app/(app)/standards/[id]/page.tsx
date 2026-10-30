"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { DocumentsPanel } from "@/components/documents";
import { Icon } from "@/components/icons";
import {
  Alert, Button, Card, ErrorState, Field, FileInput, Input, Loading, PageHeader, ReasonDialog, Spec, ToneBadge, useAction,
} from "@/components/ui";
import { api, form } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import type { MessageKey } from "@/lib/messages";
import { CAL_STATUS_TONE, STD_STATUS_TONE } from "@/lib/status";
import type { Standard, StandardCertificate, StandardUsage } from "@/lib/types";

export default function StandardDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { t, fmtDate } = useI18n();
  const { can } = useAuth();
  const std = useResource(() => api.get<Standard>(`/standards/${id}`), [id]);
  const certs = useResource(() => api.get<StandardCertificate[]>(`/standards/${id}/certificates`), [id]);
  const usages = useResource(() => (can("calibration:read") ? api.get<StandardUsage[]>(`/standards/${id}/usages`) : Promise.resolve([])), [id]);
  const [target, setTarget] = useState<null | "ACTIVE" | "RESTRICTED" | "INACTIVE">(null);

  if (std.error) return <ErrorState error={std.error} onRetry={std.reload} />;
  if (!std.data) return <Loading />;
  const s = std.data;
  const manage = can("standards:manage");
  const reload = () => { std.reload(); certs.reload(); };

  return (
    <>
      <Link href="/standards" className="mb-3 inline-flex items-center gap-1 text-[12px] text-ink-3 hover:text-ink"><Icon name="back" size={14} /> {t("std.title")}</Link>
      <PageHeader
        eyebrow={`${t(`std.cat.${s.category}` as MessageKey)} · ${s.plant.code}`}
        title={<span className="flex flex-wrap items-center gap-3"><span className="font-mono">{s.standard_code}</span>
          <ToneBadge tone={STD_STATUS_TONE[s.status]}>{t(`std.status.${s.status}`)}</ToneBadge></span>}
        actions={manage && (
          <>
            {s.control_status === "ACTIVE" && <Button onClick={() => setTarget("RESTRICTED")}>{t("std.restrict")}</Button>}
            {s.control_status !== "ACTIVE" && <Button onClick={() => setTarget("ACTIVE")}>{t("std.reactivate")}</Button>}
            {s.control_status !== "INACTIVE" && <Button variant="danger" onClick={() => setTarget("INACTIVE")}>{t("std.deactivate")}</Button>}
          </>
        )}
      >
        <p className="mt-1 text-[14px] text-ink-2">{s.description}</p>
      </PageHeader>

      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <div className="min-w-0 space-y-4">
          <Card title={t("gage.section.identification")}>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4 md:grid-cols-3">
              <Spec label={t("std.subtype")}>{s.subtype}</Spec>
              <Spec label={t("gage.field.manufacturer")}>{s.manufacturer}</Spec>
              <Spec label={t("gage.field.model")}>{s.model}</Spec>
              <Spec label={t("gage.field.serial")} mono>{s.serial_number}</Spec>
              <Spec label={t("gage.field.range")} mono>{s.range_min || s.range_max ? `${s.range_min ?? "…"} – ${s.range_max ?? "…"} ${s.unit ?? ""}` : null}</Spec>
              <Spec label={t("gage.field.resolution")} mono>{s.resolution}</Spec>
              <Spec label={t("gage.field.accuracy")} mono>{s.accuracy}</Spec>
              <Spec label={t("gage.field.location")}>{s.location}</Spec>
              <Spec label={t("std.custodian")}>{s.custodian?.full_name}</Spec>
            </dl>
          </Card>
          <Card flush title={t("cal.certificates")}>
            {certs.data?.length ? (
              <div className="overflow-x-auto">
                <table className="data-table">
                  <thead><tr><th>{t("cal.certificate.number")}</th><th>{t("cal.certificate.issuer")}</th><th>{t("std.cert.calibrationDate")}</th>
                    <th>{t("std.validUntil")}</th><th>{t("std.cert.traceability")}</th><th>{t("common.status")}</th><th /></tr></thead>
                  <tbody>
                    {certs.data.map((c) => (
                      <tr key={c.id}>
                        <td className="font-mono font-semibold">{c.certificate_number}</td>
                        <td>{c.issuer}{c.accreditation && <div className="text-[11px] text-ink-3">{c.accreditation}</div>}</td>
                        <td className="tabular">{fmtDate(c.calibration_date)}</td>
                        <td className="tabular">{fmtDate(c.valid_until)}</td>
                        <td className="max-w-[200px] truncate text-[12px]">{c.traceability ?? "—"}{c.uncertainty && <div className="text-[11px] text-ink-3">U = {c.uncertainty}</div>}</td>
                        <td><ToneBadge tone={c.status === "CURRENT" ? "ok" : "mute"}>{c.status}</ToneBadge></td>
                        <td><Button variant="ghost" className="h-7 px-2" onClick={() => api.download(`/attachments/${c.attachment_id}/download`, undefined, { open: true })}>{t("common.open")}</Button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <p className="px-4 py-4 text-[13px] text-ink-3">{t("cal.certificate.empty")}</p>}
            {manage && s.control_status !== "INACTIVE" && <AddCertificate standardId={s.id} onDone={reload} />}
          </Card>
          {can("calibration:read") && (
            <Card flush title={t("std.usages")}>
              {usages.data?.length ? (
                <div className="overflow-x-auto">
                  <table className="data-table">
                    <thead><tr><th>{t("cal.code")}</th><th>Gage ID</th><th>{t("common.date")}</th><th>{t("common.status")}</th><th>{t("std.validUntil")}</th></tr></thead>
                    <tbody>
                      {usages.data.map((u) => (
                        <tr key={u.usage_id}>
                          <td><Link className="font-mono font-semibold text-accent hover:underline" href={`/calibrations/${u.calibration_id}`}>{u.calibration_code}</Link>
                            <div><ToneBadge tone={CAL_STATUS_TONE[u.activity_status]}>{t(`cal.status.${u.activity_status}` as MessageKey)}</ToneBadge></div></td>
                          <td className="font-mono">{u.gage_code}</td>
                          <td className="tabular">{fmtDate(u.used_on)}</td>
                          <td><ToneBadge tone={STD_STATUS_TONE[u.standard_status]}>{t(`std.status.${u.standard_status}` as MessageKey)}</ToneBadge>
                            {u.is_exception && <div className="mt-1 text-[11px] text-warn">⚠ {u.exception_reason}</div>}</td>
                          <td className="tabular">{fmtDate(u.valid_until)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <p className="px-4 py-4 text-[13px] text-ink-3">{t("std.usages.empty")}</p>}
            </Card>
          )}
          <DocumentsPanel entityType="standard" entityId={s.id} canUpload={manage} />
        </div>
        <div>
          <Card title={t("gage.section.status")}>
            <div className={`mb-4 rounded-md px-3 py-2 text-[13px] font-medium ${s.usable ? "bg-ok-soft text-ok" : "bg-bad-soft text-bad"}`}>
              {s.usable ? t("status.available") : t("status.notAvailable")}
            </div>
            <dl className="grid grid-cols-2 gap-4">
              <Spec label={t("gage.field.lastCalibration")} mono>{fmtDate(s.last_calibration_date)}</Spec>
              <Spec label={t("std.validUntil")} mono>{fmtDate(s.valid_until)}</Spec>
              <Spec label={t("gage.field.frequency")} mono>{`${s.calibration_frequency_days} ${t("common.days")}`}</Spec>
            </dl>
          </Card>
        </div>
      </div>
      <ReasonDialog open={!!target} title={target ? `${t("common.status")} → ${target}` : ""} label={t("common.reasonRequired")}
        danger={target === "INACTIVE"} onClose={() => setTarget(null)}
        onConfirm={(reason) => api.post(`/standards/${s.id}/transitions`, { target, reason }).then(std.reload)} />
    </>
  );
}

function AddCertificate({ standardId, onDone }: { standardId: string; onDone: () => void }) {
  const { t } = useI18n();
  const empty = { certificate_number: "", issuer: "", accreditation: "", calibration_date: "", issue_date: "", valid_until: "", uncertainty: "", traceability: "" };
  const [f, setF] = useState(empty);
  const [file, setFile] = useState<File | null>(null);
  const [key, setKey] = useState(0);
  const { busy, error, run } = useAction();
  const s = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });
  return (
    <div className="border-t border-line bg-line-2/40 px-4 py-3">
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-ink-3">{t("std.cert.add")}</div>
      {error && <div className="mb-2"><Alert>{error}</Alert></div>}
      <div className="grid gap-2 sm:grid-cols-4">
        <Field label={t("cal.certificate.number")} required><Input value={f.certificate_number} onChange={s("certificate_number")} /></Field>
        <Field label={t("cal.certificate.issuer")} required><Input value={f.issuer} onChange={s("issuer")} /></Field>
        <Field label={t("cal.accreditation")}><Input value={f.accreditation} onChange={s("accreditation")} /></Field>
        <Field label={t("std.cert.traceability")}><Input value={f.traceability} onChange={s("traceability")} /></Field>
        <Field label={t("std.cert.calibrationDate")} required><Input type="date" className="font-mono" value={f.calibration_date} onChange={s("calibration_date")} /></Field>
        <Field label={t("cal.certificate.issueDate")} required><Input type="date" className="font-mono" value={f.issue_date} onChange={s("issue_date")} /></Field>
        <Field label={t("std.validUntil")} hint={t("std.cert.validUntilHint")}><Input type="date" className="font-mono" value={f.valid_until} onChange={s("valid_until")} /></Field>
        <Field label={t("cal.uncertainty")}><Input value={f.uncertainty} onChange={s("uncertainty")} /></Field>
        <div className="sm:col-span-3"><FileInput key={key} accept=".pdf" onFile={setFile} label="PDF" /></div>
        <Button variant="primary" disabled={!file || !f.certificate_number || !f.issuer || !f.calibration_date || !f.issue_date} loading={busy === "c"}
          onClick={() => run("c", () => api.post(`/standards/${standardId}/certificates`, form({ ...f, file })),
            () => { setF(empty); setFile(null); setKey((k) => k + 1); onDone(); })}>
          {t("common.upload")}
        </Button>
      </div>
    </div>
  );
}
