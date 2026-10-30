"use client";

import { Card, ErrorState, KpiTile, LinkButton, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import type { LabDashboard } from "@/lib/types";

export default function LabOverviewPage() {
  const { t, fmtDate } = useI18n();
  const { can } = useAuth();
  const k = useResource(() => api.get<LabDashboard>("/lab/dashboard"));
  if (k.error) return <ErrorState error={k.error} onRetry={k.reload} />;
  if (!k.data) return <Loading />;
  const d = k.data;
  const maxHours = Math.max(d.capacity.hours_per_day * d.capacity.working_days, ...d.workload_next_7_days.map((w) => w.planned_hours), 1);
  return (
    <>
      <PageHeader title={t("nav.labOverview")}
        actions={can("lab:request") && <LinkButton href="/laboratory/requests?new=1" variant="primary">+ {t("lab.request.new")}</LinkButton>}>
        <p className="mt-1 text-[12px] text-ink-3">{t("dashboard.asOf")} <span className="tabular font-medium text-ink-2">{fmtDate(d.as_of)}</span></p>
      </PageHeader>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <KpiTile label={t("lab.kpi.pending")} value={d.pending_requests} tone="warn" href="/laboratory/requests?status=SUBMITTED" />
        <KpiTile label={t("lab.kpi.open")} value={d.open_work_orders} tone="info" href="/laboratory/work-orders" />
        <KpiTile label={t("lab.kpi.inProgress")} value={d.work_orders.IN_PROGRESS ?? 0} tone="info" />
        <KpiTile label={t("lab.kpi.overdue")} value={d.overdue_work_orders} tone="bad" href="/laboratory/work-orders?overdue=1" />
        <KpiTile label={t("lab.kpi.completed")} value={d.completed_last_30_days} />
        <KpiTile label={t("lab.kpi.onTime")} value={d.on_time_rate_30_days === null ? "—" : `${d.on_time_rate_30_days} %`}
          sub={d.on_time_rate_30_days === null ? t("lab.kpi.noData") : undefined} />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_1.4fr]">
        <Card title={t("lab.kpi.capacity")}>
          <div className="tabular text-3xl font-semibold">{d.capacity.utilization_pct === null ? "—" : `${d.capacity.utilization_pct} %`}</div>
          <div className="mt-2 h-2.5 overflow-hidden rounded-sm bg-line-2">
            <div className={d.capacity.utilization_pct && d.capacity.utilization_pct > 100 ? "h-full bg-bad" : "h-full bg-accent"}
              style={{ width: `${Math.min(100, d.capacity.utilization_pct ?? 0)}%` }} />
          </div>
          <p className="mt-2 text-[12px] text-ink-3">
            {d.capacity.planned_hours} / {d.capacity.capacity_hours} {t("common.hours")} · {d.capacity.technicians} × {d.capacity.hours_per_day} h × {d.capacity.working_days} d
          </p>
          <div className="mt-4 border-t border-line pt-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-ink-3">{t("lab.kpi.response")}</div>
            <div className="mt-1 tabular text-xl font-semibold">{d.avg_response_hours_90_days === null ? "—" : `${d.avg_response_hours_90_days} h`}</div>
            <div className="text-[12px] text-ink-3">n = {d.completed_sample_90_days}</div>
          </div>
        </Card>
        <Card title={t("lab.kpi.workload")}>
          {d.workload_next_7_days.length === 0 ? <p className="text-[13px] text-ink-3">{t("lab.kpi.noData")}</p> : (
            <ul className="space-y-3">
              {d.workload_next_7_days.map((w) => (
                <li key={w.technician_id}>
                  <div className="flex justify-between text-[13px]"><span>{w.technician}</span>
                    <span className="tabular text-ink-2">{w.work_orders} OT · {w.planned_hours} h</span></div>
                  <div className="mt-1 h-2 overflow-hidden rounded-sm bg-line-2">
                    <div className="h-full bg-info" style={{ width: `${(w.planned_hours / maxHours) * 100}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
