"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { DueCell, RangeText } from "@/components/gage-bits";
import { Icon } from "@/components/icons";
import { TransitionDialog } from "@/components/transition-dialog";
import {
  Alert, Button, Card, ErrorState, LinkButton, Loading, PageHeader, Spec, StatusBadge, cx,
} from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { transitionsFrom, type TransitionOption } from "@/lib/status";
import type { AuditEvent, Gage, StatusHistory } from "@/lib/types";

export default function GageRecordPage() {
  const { id } = useParams<{ id: string }>();
  const { t, fmtDate, fmtDateTime } = useI18n();
  const { can } = useAuth();
  const gage = useResource(() => api.get<Gage>(`/gages/${id}`), [id]);
  const history = useResource(() => api.get<StatusHistory[]>(`/gages/${id}/status-history`), [id]);
  const audit = useResource(() => api.get<{ items: AuditEvent[] }>(`/gages/${id}/audit`, { limit: 100 }), [id]);
  const [option, setOption] = useState<TransitionOption | null>(null);

  if (gage.error) return <ErrorState error={gage.error} onRetry={gage.reload} />;
  if (!gage.data) return <Loading />;
  const g = gage.data;
  const options = transitionsFrom(g.control_status).filter((o) => can(o.permission));
  const retired = g.control_status === "INACTIVE";

  function refresh() {
    setOption(null);
    gage.reload();
    history.reload();
    audit.reload();
  }

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
          can("gages:update") && !retired && (
            <LinkButton href={`/gages/${g.id}/edit`}>{t("common.edit")}</LinkButton>
          )
        }
      >
        <p className="mt-1 text-[14px] text-ink-2">{g.description}</p>
      </PageHeader>

      {retired && g.retired_at && <div className="mb-4"><Alert tone="warn">{t("gage.retiredNotice", { date: fmtDate(g.retired_at) })}</Alert></div>}

      <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
        <div className="space-y-4">
          <Card title={t("gage.section.identification")}>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4 md:grid-cols-3">
              <Spec label={t("gage.field.code")} mono>{g.gage_code}</Spec>
              <Spec label={t("gage.field.type")}>{g.gage_type.name}</Spec>
              <Spec label={t("gage.field.criticality")}>{g.criticality ? t(`gage.criticality.${g.criticality}`) : null}</Spec>
              <Spec label={t("gage.field.manufacturer")}>{g.manufacturer}</Spec>
              <Spec label={t("gage.field.model")}>{g.model}</Spec>
              <Spec label={t("gage.field.serial")} mono>{g.serial_number}</Spec>
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

          <Card flush title={t("gage.section.audit")}>
            {audit.data?.items.length ? (
              <ol className="divide-y divide-line-2">
                {audit.data.items.map((e) => (
                  <li key={e.id} className="px-4 py-3">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <span className="font-mono text-[12px] font-semibold text-ink">{e.action}</span>
                      <span className="text-[12px] text-ink-3">
                        {e.actor_name ?? "—"} · <span className="tabular">{fmtDateTime(e.created_at)}</span>
                      </span>
                    </div>
                    {e.reason && <p className="mt-1 text-[12px] text-ink-2">“{e.reason}”</p>}
                    {e.changes && e.action !== "gage.created" && <ChangeList changes={e.changes} />}
                  </li>
                ))}
              </ol>
            ) : (
              <p className="px-4 py-6 text-[13px] text-ink-3">{audit.loading ? t("common.loading") : t("gage.noAudit")}</p>
            )}
          </Card>
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
              </dl>
              {options.length > 0 && (
                <div className="flex flex-col gap-2 border-t border-line pt-4">
                  {options.map((o) => (
                    <Button key={o.target} variant={o.danger ? "danger" : o.target === "ACTIVE" ? "primary" : "secondary"} onClick={() => setOption(o)}>
                      {t(o.labelKey)}
                    </Button>
                  ))}
                </div>
              )}
            </div>
          </Card>

          <Card flush title={t("gage.section.history")}>
            {history.data?.length ? (
              <ol className="relative px-4 py-3">
                {history.data.map((h, i) => (
                  <li key={h.id} className="relative pb-4 pl-5 last:pb-0">
                    {i < history.data!.length - 1 && <span className="absolute left-[4px] top-3 h-full w-px bg-line" />}
                    <span className="absolute left-0 top-1.5 size-[9px] rounded-full border-2 border-surface bg-ink-3 ring-1 ring-line" />
                    <div className="flex flex-wrap items-center gap-1.5">
                      {h.from_status && <><StatusBadge status={h.from_status} /><span className="text-ink-3">→</span></>}
                      <StatusBadge status={h.to_status} />
                    </div>
                    {h.reason && <p className="mt-1 text-[12px] text-ink-2">{h.reason}</p>}
                    <p className="mt-0.5 text-[11px] text-ink-3">
                      {h.changed_by_name ?? "—"} · <span className="tabular">{fmtDateTime(h.changed_at)}</span>
                    </p>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="px-4 py-6 text-[13px] text-ink-3">{t("gage.noHistory")}</p>
            )}
          </Card>
        </div>
      </div>

      <TransitionDialog gage={g} option={option} onClose={() => setOption(null)} onDone={refresh} />
    </>
  );
}

function ChangeList({ changes }: { changes: Record<string, unknown> }) {
  const rows = Object.entries(changes).filter(([, v]) => Array.isArray(v) && v.length === 2) as [string, [unknown, unknown]][];
  if (!rows.length) return null;
  return (
    <dl className="mt-1.5 grid gap-0.5 text-[12px]">
      {rows.map(([field, [from, to]]) => (
        <div key={field} className="flex flex-wrap gap-1.5">
          <dt className="font-mono text-ink-3">{field}</dt>
          <dd className="font-mono">
            <span className="text-ink-3 line-through">{from == null ? "∅" : String(from)}</span>
            <span className="mx-1 text-ink-3">→</span>
            <span className="text-ink">{to == null ? "∅" : String(to)}</span>
          </dd>
        </div>
      ))}
    </dl>
  );
}
