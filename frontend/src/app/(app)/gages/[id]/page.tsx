"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { DocumentsPanel } from "@/components/documents";
import { DueCell, RangeText } from "@/components/gage-bits";
import { PlanCalibrationDialog, TransferDialog } from "@/components/gage-dialogs";
import { Icon } from "@/components/icons";
import { TransitionDialog } from "@/components/transition-dialog";
import {
  Alert, Button, Card, ErrorState, LinkButton, Loading, PageHeader, Spec, StatusBadge, Tabs, ToneBadge, cx,
} from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { CAL_RESULT_TONE, CAL_STATUS_TONE, transitionsFrom, type TransitionOption } from "@/lib/status";
import type { Activity, AuditEvent, CalCertificate, Gage, Movement, StatusHistory } from "@/lib/types";

type Tab = "general" | "calibrations" | "documents" | "history";

export default function GageRecordPage() {
  const { id } = useParams<{ id: string }>();
  const { t, fmtDate } = useI18n();
  const { can } = useAuth();
  const [tab, setTab] = useState<Tab>("general");
  const gage = useResource(() => api.get<Gage>(`/gages/${id}`), [id]);
  const [option, setOption] = useState<TransitionOption | null>(null);
  const [transfer, setTransfer] = useState(false);
  const [plan, setPlan] = useState(false);

  if (gage.error) return <ErrorState error={gage.error} onRetry={gage.reload} />;
  if (!gage.data) return <Loading />;
  const g = gage.data;
  const options = transitionsFrom(g.control_status).filter((o) => can(o.permission));
  const retired = g.control_status === "INACTIVE";

  return (
    <>
      <Link href="/gages" className="mb-3 inline-flex items-center gap-1 text-[12px] text-ink-3 hover:text-ink">
        <Icon name="back" size={14} /> {t("gages.title")}
      </Link>
      <PageHeader
        eyebrow={`${g.gage_type.name} · ${g.plant.code}`}
        title={
          <span className="flex flex-wrap items-center gap-3">
            <span className="font-mono">{g.gage_code}</span>
            <StatusBadge status={g.status} large />
          </span>
        }
        actions={
          <>
            {can("calibration:manage") && !retired && (
              <Button onClick={() => setPlan(true)}>{t("gage.planCalibration")}</Button>
            )}
            {can("gages:update") && !retired && <LinkButton href={`/gages/${g.id}/edit`}>{t("common.edit")}</LinkButton>}
          </>
        }
      >
        <p className="mt-1 text-[14px] text-ink-2">{g.description}</p>
      </PageHeader>

      {retired && g.retired_at && <div className="mb-4"><Alert tone="warn">{t("gage.retiredNotice", { date: fmtDate(g.retired_at) })}</Alert></div>}

      <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
        <div className="min-w-0">
          <Tabs<Tab>
            value={tab}
            onChange={setTab}
            items={[
              { value: "general", label: t("common.general") },
              ...(can("calibration:read") ? [{ value: "calibrations" as Tab, label: t("gage.tab.calibrations") }] : []),
              { value: "documents", label: t("common.documents") },
              { value: "history", label: t("common.history") },
            ]}
          />
          {tab === "general" && <General g={g} />}
          {tab === "calibrations" && <Calibrations gageId={g.id} />}
          {tab === "documents" && (
            <DocumentsPanel entityType="gage" entityId={g.id} canUpload={can("gages:update") && !retired} />
          )}
          {tab === "history" && <History gageId={g.id} />}
        </div>

        <div className="space-y-4">
          <Card title={t("gage.section.status")}>
            <div className="space-y-4">
              <div className={cx("flex items-center gap-2 rounded-md px-3 py-2 text-[13px] font-medium",
                g.available_for_use ? "bg-ok-soft text-ok" : "bg-bad-soft text-bad")}>
                <span className={cx("size-2 rounded-full", g.available_for_use ? "bg-ok" : "bg-bad")} />
                {g.available_for_use ? t("status.available") : t("status.notAvailable")}
              </div>
              <dl className="grid grid-cols-2 gap-4">
                <Spec label={t("gage.field.lastCalibration")} mono>{fmtDate(g.last_calibration_date)}</Spec>
                <Spec label={t("gage.field.frequency")} mono>{`${g.calibration_frequency_days} ${t("common.days")}`}</Spec>
                <div className="col-span-2">
                  <dt className="text-[11px] font-medium uppercase tracking-wide text-ink-3">{t("gage.field.nextDue")}</dt>
                  <dd className="mt-0.5"><DueCell gage={g} /></dd>
                </div>
                <Spec label={t("gage.field.lastVerification")} mono>{fmtDate(g.last_verification_date)}</Spec>
              </dl>
              {(options.length > 0 || (can("gages:transfer") && !retired)) && (
                <div className="flex flex-col gap-2 border-t border-line pt-4">
                  {can("gages:transfer") && !retired && <Button onClick={() => setTransfer(true)}>{t("gage.transfer")}</Button>}
                  {options.map((o) => (
                    <Button key={o.target} variant={o.danger ? "danger" : o.target === "ACTIVE" ? "primary" : "secondary"} onClick={() => setOption(o)}>
                      {t(o.labelKey)}
                    </Button>
                  ))}
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>

      <TransitionDialog gage={g} option={option} onClose={() => setOption(null)} onDone={() => { setOption(null); gage.reload(); }} />
      <TransferDialog gage={g} open={transfer} onClose={() => setTransfer(false)} onDone={() => { setTransfer(false); gage.reload(); }} />
      <PlanCalibrationDialog gageId={g.id} open={plan} onClose={() => setPlan(false)} />
    </>
  );
}

function General({ g }: { g: Gage }) {
  const { t, fmtDate } = useI18n();
  return (
    <div className="space-y-4">
      <Card title={t("gage.section.identification")}>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-4 md:grid-cols-3">
          <Spec label={t("gage.field.code")} mono>{g.gage_code}</Spec>
          <Spec label={t("gage.field.type")}>{g.gage_type.name}</Spec>
          <Spec label={t("gage.field.criticality")}>{g.criticality ? t(`gage.criticality.${g.criticality}`) : null}</Spec>
          <Spec label={t("gage.field.manufacturer")}>{g.manufacturer}</Spec>
          <Spec label={t("gage.field.model")}>{g.model}</Spec>
          <Spec label={t("gage.field.serial")} mono>{g.serial_number}</Spec>
          <Spec label={t("gage.field.acquisition")} mono>{fmtDate(g.acquisition_date)}</Spec>
          <Spec label={t("gage.field.inService")} mono>{fmtDate(g.in_service_date)}</Spec>
        </dl>
      </Card>
      <Card title={t("gage.section.specs")}>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-4 md:grid-cols-3">
          <Spec label={t("gage.field.range")}><RangeText gage={g} /></Spec>
          <Spec label={t("gage.field.resolution")} mono>{g.resolution ? `${g.resolution} ${g.unit ?? ""}` : null}</Spec>
          <Spec label={t("gage.field.accuracy")} mono>{g.accuracy}</Spec>
        </dl>
      </Card>
      <Card title={t("gage.section.assignment")}>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-4 md:grid-cols-4">
          <Spec label={t("gage.field.plant")}>{`${g.plant.code} — ${g.plant.name}`}</Spec>
          <Spec label={t("gage.field.department")}>{g.department ? `${g.department.code} — ${g.department.name}` : null}</Spec>
          <Spec label={t("gage.field.location")}>{g.location}</Spec>
          <Spec label={t("gage.field.responsible")}>{g.responsible?.full_name}</Spec>
        </dl>
        {g.notes && <p className="mt-4 whitespace-pre-wrap border-t border-line pt-3 text-[13px] text-ink-2">{g.notes}</p>}
      </Card>
    </div>
  );
}

function Calibrations({ gageId }: { gageId: string }) {
  const { t, fmtDate } = useI18n();
  const data = useResource(() => api.get<{ activities: Activity[]; certificates: CalCertificate[] }>(`/gages/${gageId}/calibration-summary`), [gageId]);
  if (!data.data) return <Loading />;
  return (
    <div className="space-y-4">
      <Card flush title={t("gage.tab.calibrations")}>
        {data.data.activities.length === 0 ? (
          <p className="px-4 py-5 text-[13px] text-ink-3">{t("cal.empty")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead><tr><th>{t("cal.code")}</th><th>{t("cal.type")}</th><th>{t("cal.performed")}</th><th>{t("common.result")}</th><th>{t("common.status")}</th><th>{t("cal.dueDate")}</th></tr></thead>
              <tbody>
                {data.data.activities.map((a) => (
                  <tr key={a.id}>
                    <td><Link className="font-mono text-[13px] font-semibold text-accent hover:underline" href={`/calibrations/${a.id}`}>{a.calibration_code}</Link></td>
                    <td>{t(`cal.type.${a.activity_type}`)}</td>
                    <td className="tabular">{fmtDate(a.performed_date)}</td>
                    <td>{a.result ? <ToneBadge tone={CAL_RESULT_TONE[a.result]}>{t(`cal.result.${a.result}`)}</ToneBadge> : "—"}</td>
                    <td><ToneBadge tone={CAL_STATUS_TONE[a.status]}>{t(`cal.status.${a.status}`)}</ToneBadge></td>
                    <td className="tabular">{fmtDate(a.due_date)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <Card flush title={t("cal.certificates")}>
        {data.data.certificates.length === 0 ? (
          <p className="px-4 py-5 text-[13px] text-ink-3">{t("cal.certificate.empty")}</p>
        ) : (
          <ul className="divide-y divide-line-2">
            {data.data.certificates.map((c) => (
              <li key={c.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
                <span className="font-mono text-[13px] font-semibold">{c.certificate_number}</span>
                <span className="text-[12px] text-ink-2">{c.issuer} · {fmtDate(c.issue_date)}</span>
                <ToneBadge tone={c.status === "CURRENT" ? "ok" : "mute"}>{c.status}</ToneBadge>
                <Button variant="ghost" className="ml-auto h-7 px-2" onClick={() => api.download(`/attachments/${c.attachment_id}/download`, undefined, { open: true })}>
                  {t("common.open")}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function History({ gageId }: { gageId: string }) {
  const { t, fmtDateTime } = useI18n();
  const history = useResource(() => api.get<StatusHistory[]>(`/gages/${gageId}/status-history`), [gageId]);
  const moves = useResource(() => api.get<Movement[]>(`/gages/${gageId}/movements`), [gageId]);
  const audit = useResource(() => api.get<{ items: AuditEvent[] }>(`/gages/${gageId}/audit`, { limit: 200 }), [gageId]);
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card flush title={t("gage.section.history")}>
        {history.data?.length ? (
          <ol className="px-4 py-3">
            {history.data.map((h) => (
              <li key={h.id} className="border-l-2 border-line pb-3 pl-3 last:pb-0">
                <div className="flex flex-wrap items-center gap-1.5">
                  {h.from_status && <><StatusBadge status={h.from_status} /><span className="text-ink-3">→</span></>}
                  <StatusBadge status={h.to_status} />
                </div>
                {h.reason && <p className="mt-1 text-[12px] text-ink-2">{h.reason}</p>}
                <p className="mt-0.5 text-[11px] text-ink-3">{h.changed_by_name ?? "—"} · <span className="tabular">{fmtDateTime(h.changed_at)}</span></p>
              </li>
            ))}
          </ol>
        ) : <p className="px-4 py-5 text-[13px] text-ink-3">{t("gage.noHistory")}</p>}
      </Card>
      <Card flush title={t("gage.movements")}>
        {moves.data?.length ? (
          <ol className="divide-y divide-line-2">
            {moves.data.map((m) => (
              <li key={m.id} className="px-4 py-2.5">
                {Object.entries(m.changes).map(([k, [from, to]]) => (
                  <div key={k} className="text-[12px]">
                    <span className="font-mono text-ink-3">{k}</span>{" "}
                    <span className="text-ink-3 line-through">{from ?? "∅"}</span> → <span className="font-medium">{to ?? "∅"}</span>
                  </div>
                ))}
                <p className="mt-1 text-[12px] text-ink-2">“{m.reason}”</p>
                <p className="text-[11px] text-ink-3">{m.moved_by_name} · {fmtDateTime(m.moved_at)}</p>
              </li>
            ))}
          </ol>
        ) : <p className="px-4 py-5 text-[13px] text-ink-3">{t("gage.noMovements")}</p>}
      </Card>
      <Card flush title={t("gage.section.audit")} className="lg:col-span-2">
        {audit.data?.items.length ? (
          <ol className="divide-y divide-line-2">
            {audit.data.items.map((e) => (
              <li key={e.id} className="px-4 py-2.5">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="font-mono text-[12px] font-semibold">{e.action}</span>
                  <span className="text-[12px] text-ink-3">{e.actor_name ?? "—"} · <span className="tabular">{fmtDateTime(e.created_at)}</span></span>
                </div>
                {e.reason && <p className="mt-1 text-[12px] text-ink-2">“{e.reason}”</p>}
                {e.changes && e.action !== "gage.created" && (
                  <code className="mt-1 block break-all text-[11px] text-ink-2">{JSON.stringify(e.changes)}</code>
                )}
              </li>
            ))}
          </ol>
        ) : <p className="px-4 py-5 text-[13px] text-ink-3">{t("gage.noAudit")}</p>}
      </Card>
    </div>
  );
}
