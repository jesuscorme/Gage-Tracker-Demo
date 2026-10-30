"use client";

import Link from "next/link";
import { useState } from "react";
import { Button, Card, Check, EmptyState, ErrorState, Loading, PageHeader, ToneBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import type { MeasurementReport } from "@/lib/types";

export default function ReportsPage() {
  const { t, fmtDateTime } = useI18n();
  const [all, setAll] = useState(false);
  const list = useResource(() => api.get<MeasurementReport[]>("/lab/reports", { include_superseded: all }), [all]);
  return (
    <>
      <PageHeader title={t("nav.labReports")} actions={<Check label={t("lab.report.superseded")} checked={all} onChange={setAll} />} />
      <Card flush>
        {list.error ? <div className="px-4"><ErrorState error={list.error} onRetry={list.reload} /></div>
          : !list.data ? <div className="px-4"><Loading /></div>
          : list.data.length === 0 ? <EmptyState>{t("lab.report.empty")}</EmptyState>
          : (
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead><tr><th>{t("nav.labReports")}</th><th>{t("lab.wo.code")}</th><th>{t("common.part")}</th><th>{t("lab.request.customer")}</th>
                  <th>{t("lab.report.acceptance")}</th><th>{t("common.date")}</th><th /></tr></thead>
                <tbody>
                  {list.data.map((r) => (
                    <tr key={r.id} className={r.status === "SUPERSEDED" ? "text-ink-3" : ""}>
                      <td><Link href={`/laboratory/reports/${r.id}`} className="font-mono text-[13px] font-semibold text-accent hover:underline">{r.report_code}</Link>
                        <span className="ml-1 text-[11px] text-ink-3">rev {r.revision}</span></td>
                      <td className="font-mono text-[12px]">{r.snapshot.work_order}</td>
                      <td className="font-mono text-[12px]">{r.snapshot.part_number ?? "—"}</td>
                      <td className="text-[12px]">{r.snapshot.customer ?? "—"}</td>
                      <td><ToneBadge tone={r.acceptance === "ACCEPTED" ? "ok" : "bad"}>{t(`lab.report.${r.acceptance}`)}</ToneBadge></td>
                      <td className="tabular text-[12px]">{fmtDateTime(r.issued_at)}</td>
                      <td><Button variant="ghost" className="h-7 px-2" onClick={() => api.download(`/attachments/${r.attachment_id}/download`, undefined, { open: true })}>PDF</Button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </Card>
    </>
  );
}
