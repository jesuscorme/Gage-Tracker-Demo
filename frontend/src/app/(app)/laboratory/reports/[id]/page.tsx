"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Icon } from "@/components/icons";
import { Button, Card, ErrorState, Loading, PageHeader, Spec, ToneBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import type { MeasurementReport } from "@/lib/types";

export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const { t, fmtDate, fmtDateTime } = useI18n();
  const rep = useResource(() => api.get<MeasurementReport>(`/lab/reports/${id}`), [id]);
  if (rep.error) return <ErrorState error={rep.error} onRetry={rep.reload} />;
  if (!rep.data) return <Loading />;
  const r = rep.data;
  const s = r.snapshot;
  return (
    <>
      <Link href="/laboratory/reports" className="mb-3 inline-flex items-center gap-1 text-[12px] text-ink-3 hover:text-ink"><Icon name="back" size={14} /> {t("nav.labReports")}</Link>
      <PageHeader eyebrow={s.service}
        title={<span className="flex flex-wrap items-center gap-3"><span className="font-mono">{r.report_code}</span>
          <span className="text-[14px] text-ink-3">rev {r.revision}</span>
          <ToneBadge tone={r.acceptance === "ACCEPTED" ? "ok" : "bad"}>{t(`lab.report.${r.acceptance}`)}</ToneBadge>
          {r.status === "SUPERSEDED" && <ToneBadge tone="mute">{t("lab.report.superseded")}</ToneBadge>}</span>}
        actions={<Button variant="primary" onClick={() => api.download(`/attachments/${r.attachment_id}/download`, undefined, { filename: `${r.report_code}-R${r.revision}.pdf` })}>
          <Icon name="download" size={14} /> PDF</Button>} />
      <Card title={t("common.general")}>
        <dl className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Spec label={t("lab.request.customer")}>{s.customer}</Spec>
          <Spec label={t("lab.wo.code")} mono>{`${s.request} / ${s.work_order}`}</Spec>
          <Spec label={t("common.part")} mono>{s.part_number ? `${s.part_number} rev ${s.part_revision ?? "—"}` : null}</Spec>
          <Spec label={t("common.date")} mono>{fmtDate(s.issued_on)}</Spec>
          <Spec label={t("lab.wo.technician")}>{s.technician}</Spec>
          <Spec label={t("cal.reviewer")}>{s.reviewer}</Spec>
          <Spec label={t("lab.wo.equipment")} mono>{s.equipment.join(", ")}</Spec>
          <Spec label={t("cal.releasedAt")}>{fmtDateTime(r.issued_at)}</Spec>
        </dl>
        {r.observations && <p className="mt-3 border-t border-line pt-3 text-[13px] text-ink-2">{r.observations}</p>}
        {r.revision_reason && <p className="mt-2 text-[12px] text-ink-3">↺ {r.revision_reason}</p>}
      </Card>
      <Card flush className="mt-4" title={t("lab.dim.title")}>
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead><tr><th>{t("common.part")}</th><th>{t("lab.dim.sample")}</th><th>{t("lab.dim.number")}</th><th>{t("lab.dim.characteristic")}</th>
              <th>{t("cal.point.nominal")}</th><th>LSL</th><th>USL</th><th>{t("cal.point.measured")}</th><th>Gage</th><th>{t("common.result")}</th></tr></thead>
            <tbody>
              {s.results.map((x, i) => (
                <tr key={i}>
                  <td className="font-mono text-[12px]">{x.part_number}</td><td className="font-mono text-[12px]">{x.sample ?? "—"}</td>
                  <td className="font-mono">{x.number}</td><td>{x.characteristic}</td>
                  <td className="font-mono tabular">{x.nominal}</td><td className="font-mono tabular">{x.lower}</td><td className="font-mono tabular">{x.upper}</td>
                  <td className="font-mono tabular font-semibold">{x.measured} {x.unit}</td><td className="font-mono text-[12px]">{x.gage}</td>
                  <td><ToneBadge tone={x.result === "OK" ? "ok" : "bad"}>{x.result}</ToneBadge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
