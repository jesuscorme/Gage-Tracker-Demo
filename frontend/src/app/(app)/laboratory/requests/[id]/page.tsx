"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { DocumentsPanel } from "@/components/documents";
import { Icon } from "@/components/icons";
import {
  Alert, Button, Card, ErrorState, Field, Input, Loading, PageHeader, ReasonDialog, Spec, ToneBadge, useAction,
} from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { PRIORITY_TONE, REQ_STATUS_TONE } from "@/lib/status";
import type { ServiceRequest, WorkOrderDetail } from "@/lib/types";

export default function RequestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { t, fmtDate, fmtDateTime } = useI18n();
  const { can, me } = useAuth();
  const router = useRouter();
  const req = useResource(() => api.get<ServiceRequest>(`/lab/requests/${id}`), [id]);
  const [committed, setCommitted] = useState("");
  const [dialog, setDialog] = useState<null | "reject" | "cancel">(null);
  const { busy, error, run } = useAction();
  if (req.error) return <ErrorState error={req.error} onRetry={req.reload} />;
  if (!req.data) return <Loading />;
  const r = req.data;
  const manage = can("lab:manage");

  return (
    <>
      <Link href="/laboratory/requests" className="mb-3 inline-flex items-center gap-1 text-[12px] text-ink-3 hover:text-ink"><Icon name="back" size={14} /> {t("nav.labRequests")}</Link>
      <PageHeader eyebrow={r.service_name}
        title={<span className="flex flex-wrap items-center gap-3"><span className="font-mono">{r.request_code}</span>
          <ToneBadge tone={REQ_STATUS_TONE[r.status]}>{t(`lab.rstatus.${r.status}`)}</ToneBadge>
          <ToneBadge tone={PRIORITY_TONE[r.priority]}>{t(`lab.priority.${r.priority}`)}</ToneBadge></span>}
        actions={["SUBMITTED", "APPROVED"].includes(r.status) && !r.work_order_id && (manage || r.requester_name === me?.full_name) && (
          <Button variant="danger" onClick={() => setDialog("cancel")}>{t("common.cancel")}</Button>
        )} />
      {error && <div className="mb-4"><Alert>{error}</Alert></div>}
      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <div className="space-y-4">
          <Card title={t("common.general")}>
            <dl className="grid grid-cols-2 gap-4 md:grid-cols-3">
              <Spec label={t("lab.request.requester")}>{r.requester_name}</Spec>
              <Spec label={t("lab.request.customer")}>{`${t(`lab.request.${r.customer_type}`)}${r.customer_name ? ` · ${r.customer_name}` : ""}`}</Spec>
              <Spec label={t("common.part")} mono>{r.part_number ? `${r.part_number}${r.part_revision ? ` rev ${r.part_revision}` : ""}` : null}</Spec>
              <Spec label={t("lab.request.quantity")} mono>{String(r.quantity)}</Spec>
              <Spec label={t("lab.request.requested")} mono>{fmtDate(r.requested_date)}</Spec>
              <Spec label={t("lab.request.committed")} mono>{fmtDate(r.committed_date)}</Spec>
            </dl>
            <p className="mt-4 whitespace-pre-wrap border-t border-line pt-3 text-[13px]">{r.description}</p>
            {r.decision_comment && <p className="mt-2 text-[12px] text-ink-2">“{r.decision_comment}”</p>}
            <p className="mt-2 text-[11px] text-ink-3">{fmtDateTime(r.created_at)}</p>
          </Card>
          <DocumentsPanel entityType="service_request" entityId={r.id} canUpload={["SUBMITTED", "APPROVED", "IN_PROGRESS"].includes(r.status)} />
        </div>
        <div className="space-y-4">
          {manage && r.status === "SUBMITTED" && (
            <Card title={t("lab.request.approve")}>
              <Field label={t("lab.request.committed")} required>
                <Input type="date" className="font-mono" value={committed} onChange={(e) => setCommitted(e.target.value)} />
              </Field>
              <div className="mt-3 flex gap-2">
                <Button variant="primary" disabled={!committed} loading={busy === "ok"}
                  onClick={() => run("ok", () => api.post(`/lab/requests/${r.id}/decision`, { approve: true, committed_date: committed }), req.reload)}>
                  {t("lab.request.approve")}
                </Button>
                <Button onClick={() => setDialog("reject")}>{t("lab.request.reject")}</Button>
              </div>
            </Card>
          )}
          {(r.work_order_id || (manage && r.status === "APPROVED")) && (
            <Card title={t("lab.wo.code")}>
              {r.work_order_id ? (
                <Link href={`/laboratory/work-orders/${r.work_order_id}`} className="font-mono text-[14px] font-semibold text-accent hover:underline">{r.work_order_code}</Link>
              ) : (
                <Button variant="primary" loading={busy === "wo"} onClick={() => run("wo", async () => {
                  const wo = await api.post<WorkOrderDetail>("/lab/work-orders", { service_request_id: r.id });
                  router.push(`/laboratory/work-orders/${wo.id}`);
                })}>{t("lab.request.toWorkOrder")}</Button>
              )}
            </Card>
          )}
        </div>
      </div>
      <ReasonDialog open={dialog === "reject"} title={t("lab.request.reject")} label={t("common.reasonRequired")} danger
        onClose={() => setDialog(null)} onConfirm={(c) => api.post(`/lab/requests/${r.id}/decision`, { approve: false, comment: c }).then(req.reload)} />
      <ReasonDialog open={dialog === "cancel"} title={t("common.cancel")} label={t("common.reasonRequired")} danger
        onClose={() => setDialog(null)} onConfirm={(reason) => api.post(`/lab/requests/${r.id}/cancel`, { reason }).then(req.reload)} />
    </>
  );
}
