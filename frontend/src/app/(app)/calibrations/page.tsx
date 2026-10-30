"use client";

import Link from "next/link";
import { useState } from "react";
import { DueCell } from "@/components/gage-bits";
import { PlanCalibrationDialog } from "@/components/gage-dialogs";
import {
  Button, Card, EmptyState, ErrorState, Input, KpiTile, LinkButton, Loading, PageHeader, Select, StatusBadge, ToneBadge,
} from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { ACTIVITY_TYPES, CAL_RESULT_TONE, CAL_STATUS_TONE } from "@/lib/status";
import type { Activity, ActivityStatus, CalOverview, Gage, Page } from "@/lib/types";

const STATUSES: ActivityStatus[] = ["PLANNED", "REQUESTED", "SCHEDULED", "IN_PROGRESS", "PENDING_REVIEW",
  "PENDING_APPROVAL", "APPROVED", "RELEASED", "CANCELLED"];
const OPEN = ["PLANNED", "REQUESTED", "SCHEDULED", "IN_PROGRESS", "PENDING_REVIEW", "PENDING_APPROVAL", "APPROVED"];

export default function CalibrationsPage() {
  const { t, fmtDate } = useI18n();
  const { can } = useAuth();
  const [status, setStatus] = useState("OPEN");
  const [type, setType] = useState("");
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [plan, setPlan] = useState(false);
  const ov = useResource(() => api.get<CalOverview>("/calibrations/overview"));
  const list = useResource(
    () => api.get<{ items: Activity[]; total: number }>("/calibrations", {
      status: status === "OPEN" ? OPEN : status ? [status] : undefined, activity_type: type, q, page_size: 100,
    }),
    [status, type, q],
  );
  const gages = useResource(() => (plan ? api.get<Page<Gage>>("/gages", { page_size: 200 }) : Promise.resolve(null)), [plan]);

  return (
    <>
      <PageHeader
        title={t("cal.title")}
        actions={
          <>
            <LinkButton href="/calibrations/calendar">{t("nav.calendar")}</LinkButton>
            {can("calibration:manage") && <Button variant="primary" onClick={() => setPlan(true)}>+ {t("cal.new")}</Button>}
          </>
        }
      />
      {ov.error ? <ErrorState error={ov.error} onRetry={ov.reload} /> : !ov.data ? <Loading /> : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
            <KpiTile label={t("cal.kpi.overdue")} value={ov.data.gages_overdue} tone="bad" href="/gages?status=OVERDUE" />
            <KpiTile label={t("cal.kpi.dueSoon")} value={ov.data.gages_due_soon} tone="warn" href="/gages?status=DUE_SOON" />
            <KpiTile label={t("cal.kpi.pending")} value={ov.data.pending} />
            <KpiTile label={t("cal.kpi.inProgress")} value={ov.data.in_progress} tone="info" />
            <KpiTile label={t("cal.kpi.review")} value={ov.data.pending_review} tone="warn" />
            <KpiTile label={t("cal.kpi.approval")} value={ov.data.pending_approval} tone="warn" />
            <KpiTile label={t("cal.kpi.release")} value={ov.data.pending_release} tone="info" />
          </div>
          <Card flush title={t("cal.unplanned")} className="mt-4">
            {ov.data.unplanned_due.length === 0 ? (
              <p className="px-4 py-4 text-[13px] text-ink-3">{t("cal.unplannedEmpty")}</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="data-table">
                  <tbody>
                    {ov.data.unplanned_due.map((g) => (
                      <tr key={g.id}>
                        <td><Link href={`/gages/${g.id}`} className="font-mono text-[13px] font-semibold text-accent hover:underline">{g.gage_code}</Link></td>
                        <td className="max-w-[320px] truncate">{g.description}</td>
                        <td><DueCell gage={g} /></td>
                        <td><StatusBadge status={g.status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}

      <Card flush className="mt-4">
        <form className="grid gap-2 border-b border-line p-3 sm:grid-cols-[minmax(200px,2fr)_1fr_1fr]"
          onSubmit={(e) => { e.preventDefault(); setQ(search.trim()); }}>
          <Input type="search" placeholder="CAL-…, Gage ID, proveedor" value={search} onChange={(e) => setSearch(e.target.value)}
            onBlur={() => setQ(search.trim())} aria-label={t("common.search")} />
          <Select value={status} onChange={(e) => setStatus(e.target.value)} aria-label={t("common.status")}>
            <option value="OPEN">{t("common.status")}: {t("cal.kpi.pending")} / {t("cal.kpi.inProgress")}</option>
            <option value="">{t("common.status")}: {t("common.all")}</option>
            {STATUSES.map((s) => <option key={s} value={s}>{t(`cal.status.${s}`)}</option>)}
          </Select>
          <Select value={type} onChange={(e) => setType(e.target.value)} aria-label={t("cal.type")}>
            <option value="">{t("cal.type")}: {t("common.all")}</option>
            {ACTIVITY_TYPES.map((a) => <option key={a} value={a}>{t(`cal.type.${a}`)}</option>)}
          </Select>
        </form>
        {list.error ? <div className="px-4"><ErrorState error={list.error} onRetry={list.reload} /></div>
          : !list.data ? <div className="px-4"><Loading /></div>
          : list.data.items.length === 0 ? <EmptyState>{t("cal.empty")}</EmptyState>
          : (
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t("cal.code")}</th><th>Gage ID</th><th>{t("cal.type")}</th>
                    <th className="hidden md:table-cell">{t("cal.planned")}</th>
                    <th className="hidden lg:table-cell">{t("cal.provider")} / {t("cal.technician")}</th>
                    <th>{t("common.result")}</th><th>{t("common.status")}</th>
                  </tr>
                </thead>
                <tbody>
                  {list.data.items.map((a) => (
                    <tr key={a.id}>
                      <td><Link href={`/calibrations/${a.id}`} className="font-mono text-[13px] font-semibold text-accent hover:underline">{a.calibration_code}</Link></td>
                      <td>
                        <div className="font-mono text-[13px]">{a.gage_code}</div>
                        <div className="max-w-[220px] truncate text-[11px] text-ink-3">{a.gage_description}</div>
                      </td>
                      <td className="text-[12px]">{t(`cal.type.${a.activity_type}`)}</td>
                      <td className="hidden tabular md:table-cell">{fmtDate(a.scheduled_date ?? a.planned_date)}</td>
                      <td className="hidden max-w-[200px] truncate text-[12px] text-ink-2 lg:table-cell">{a.provider_name ?? a.technician_name ?? "—"}</td>
                      <td>{a.result ? <ToneBadge tone={CAL_RESULT_TONE[a.result]}>{t(`cal.result.${a.result}`)}</ToneBadge> : "—"}</td>
                      <td><ToneBadge tone={CAL_STATUS_TONE[a.status]}>{t(`cal.status.${a.status}`)}</ToneBadge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </Card>
      <PlanCalibrationDialog gages={gages.data?.items.filter((g) => g.control_status !== "INACTIVE")} open={plan} onClose={() => setPlan(false)} />
    </>
  );
}
