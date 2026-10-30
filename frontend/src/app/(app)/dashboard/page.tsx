"use client";

import Link from "next/link";
import { DueCell } from "@/components/gage-bits";
import { Card, EmptyState, ErrorState, LinkButton, Loading, PageHeader, StatusBadge, StatusDot, cx } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { GAGE_STATUSES, STATUS_TONE } from "@/lib/status";
import type { DashboardSummary, GageStatus } from "@/lib/types";

const BAR: Record<string, string> = {
  ok: "bg-ok", warn: "bg-warn", bad: "bg-bad", block: "bg-block", info: "bg-info", mute: "bg-mute",
};

export default function DashboardPage() {
  const { t, fmtDate } = useI18n();
  const { can, membership } = useAuth();
  const { data, error, loading, reload } = useResource(() => api.get<DashboardSummary>("/dashboard/summary"));

  if (loading && !data) return <Loading />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!data) return null;

  const inService = GAGE_STATUSES.filter((s) => s !== "INACTIVE");
  const empty = data.total_in_service === 0 && data.by_status.INACTIVE === 0;

  return (
    <>
      <PageHeader
        eyebrow={membership?.organization_name}
        title={t("dashboard.title")}
        actions={can("gages:create") && <LinkButton href="/gages/new" variant="primary">+ {t("gages.new")}</LinkButton>}
      >
        <p className="mt-1 text-[12px] text-ink-3">
          {t("dashboard.asOf")} <span className="tabular font-medium text-ink-2">{fmtDate(data.as_of)}</span>
          {data.plant_scope && <> · {t("dashboard.scope")}</>}
        </p>
      </PageHeader>

      {empty ? (
        <Card>
          <EmptyState action={can("gages:create") && <LinkButton href="/gages/new" variant="primary">{t("dashboard.emptyCta")}</LinkButton>}>
            {t("dashboard.empty")}
          </EmptyState>
        </Card>
      ) : (
        <div className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-[1.2fr_1.2fr_3fr]">
            <Kpi label={t("dashboard.inService")} value={data.total_in_service} href="/gages" />
            <Kpi
              label={t("dashboard.available")}
              value={data.available}
              sub={data.total_in_service ? `${Math.round((data.available / data.total_in_service) * 100)} %` : undefined}
              href="/gages?available=true"
            />
            <div className="rounded-lg border border-line bg-surface p-4 sm:col-span-2 xl:col-span-1">
              <div className="flex h-2.5 overflow-hidden rounded-sm bg-line-2" role="img" aria-label="status distribution">
                {inService.map((s) =>
                  data.by_status[s] ? (
                    <div key={s} className={BAR[STATUS_TONE[s]]} style={{ width: `${(data.by_status[s] / data.total_in_service) * 100}%` }} />
                  ) : null,
                )}
              </div>
              <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-3">
                {GAGE_STATUSES.map((s) => (
                  <Link key={s} href={`/gages?status=${s}`} className="flex items-center justify-between gap-2 rounded px-1 py-0.5 hover:bg-line-2">
                    <span className="flex items-center gap-2 text-[12px] text-ink-2">
                      <StatusDot status={s} /> {t(`status.${s}`)}
                    </span>
                    <span className="tabular text-[13px] font-semibold">{data.by_status[s]}</span>
                  </Link>
                ))}
              </div>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            {(["OVERDUE", "DUE_SOON", "OUT_OF_SERVICE"] as GageStatus[]).map((s) => (
              <AlertTile key={s} status={s} value={data.by_status[s]} />
            ))}
          </div>

          <Card
            flush
            title={t("dashboard.upcoming")}
            actions={<span className="text-[12px] text-ink-3">{t("dashboard.upcomingHint", { days: data.due_soon_days })}</span>}
          >
            {data.upcoming.length === 0 ? (
              <EmptyState>{t("dashboard.noUpcoming")}</EmptyState>
            ) : (
              <div className="overflow-x-auto">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t("gages.col.id")}</th>
                      <th>{t("gages.col.description")}</th>
                      <th className="hidden md:table-cell">{t("gages.col.plant")}</th>
                      <th>{t("gages.col.due")}</th>
                      <th>{t("gages.col.status")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.upcoming.map((g) => (
                      <tr key={g.id}>
                        <td>
                          <Link href={`/gages/${g.id}`} className="font-mono text-[13px] font-semibold text-accent hover:underline">
                            {g.gage_code}
                          </Link>
                        </td>
                        <td className="max-w-[320px] truncate">{g.description}</td>
                        <td className="hidden font-mono text-[12px] text-ink-2 md:table-cell">
                          {g.plant.code}
                          {g.department && ` / ${g.department.code}`}
                        </td>
                        <td><DueCell gage={g} /></td>
                        <td><StatusBadge status={g.status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}
    </>
  );
}

function Kpi({ label, value, sub, href }: { label: string; value: number; sub?: string; href: string }) {
  return (
    <Link href={href} className="group rounded-lg border border-line bg-surface p-4 hover:border-accent/40">
      <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-ink-3">{label}</div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="tabular text-3xl font-semibold">{value}</span>
        {sub && <span className="tabular text-[13px] text-ink-3">{sub}</span>}
      </div>
    </Link>
  );
}

function AlertTile({ status, value }: { status: GageStatus; value: number }) {
  const { t } = useI18n();
  const tone = STATUS_TONE[status];
  return (
    <Link
      href={`/gages?status=${status}`}
      className={cx(
        "flex items-center justify-between rounded-lg border bg-surface px-4 py-3 hover:bg-line-2/40",
        value > 0 ? "border-l-4" : "border-line",
        value > 0 && { bad: "border-bad/40 border-l-bad", warn: "border-warn/40 border-l-warn", block: "border-block/40 border-l-block" }[tone],
      )}
    >
      <StatusBadge status={status} />
      <span className={cx("tabular text-2xl font-semibold", value === 0 && "text-ink-3")}>{value}</span>
    </Link>
  );
}
