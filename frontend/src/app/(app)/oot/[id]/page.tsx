"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { CustomFieldsCard } from "@/components/custom-fields";
import { DocumentsPanel } from "@/components/documents";
import {
  Alert, Button, Card, EmptyState, ErrorState, Field, Input, Loading, Modal, PageHeader, ReasonDialog, Select, Spec, Tabs,
  Textarea, ToneBadge, useAction,
} from "@/components/ui";
import { IssueList, WorkflowPanel } from "@/components/workflow";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { useUsers } from "@/lib/lookups";
import { ASSESSMENT_TONE } from "@/lib/status-b3";
import type { CalHistoryRow, OotAction, OotCase, OotItem, WorkflowState } from "@/lib/types-b3";

type Tab = "case" | "analysis" | "actions" | "calibrations";
const FIELDS = ["risk_assessment", "investigation_scope", "reinspection", "containment", "disposition", "corrective_actions",
  "customer_notification"] as const;
const LABEL: Record<(typeof FIELDS)[number], string> = {
  risk_assessment: "oot.riskAssessment", investigation_scope: "oot.scope", reinspection: "oot.reinspection",
  containment: "oot.containment", disposition: "oot.disposition", corrective_actions: "oot.corrective",
  customer_notification: "oot.customerNotification",
};

export default function OotCasePage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("case");
  const c = useResource(() => api.get<OotCase>(`/oot/cases/${id}`), [id]);
  const wf = useResource(() => api.get<WorkflowState>(`/workflows/oot_case/${id}`), [id]);
  const users = useUsers();
  if (c.error) return <ErrorState error={c.error} onRetry={c.reload} />;
  if (!c.data || !wf.data) return <Loading />;
  const caps = new Set(wf.data.capabilities);
  const refresh = () => { c.reload(); wf.reload(); };
  return (
    <>
      <PageHeader eyebrow={t("oot.title")} title={`${c.data.case_code} · ${c.data.gage_code}`}
        actions={<ToneBadge tone={c.data.status === "CLOSED" ? "ok" : "warn"}>{c.data.status}</ToneBadge>} />
      <Tabs value={tab} onChange={setTab} items={[
        { value: "case", label: t("oot.tab.case") }, { value: "analysis", label: t("oot.tab.analysis") },
        { value: "actions", label: t("oot.tab.actions") }, { value: "calibrations", label: t("oot.tab.calibrations") },
      ]} />
      <div className="mt-4">
        {tab === "case" && <CaseTab c={c.data} caps={caps} users={users.names} userList={users.list} onChange={refresh} />}
        {tab === "analysis" && <AnalysisTab c={c.data} caps={caps} onChange={refresh} />}
        {tab === "actions" && <ActionsTab c={c.data} caps={caps} users={users.names} userList={users.list} />}
        {tab === "calibrations" && <CalTab id={id} />}
      </div>
    </>
  );
}

function CaseTab({ c, caps, users, userList, onChange }: {
  c: OotCase; caps: Set<string>; users: Record<string, string>; userList: { id: string; full_name: string }[]; onChange: () => void;
}) {
  const { t, fmtDate, fmtDateTime } = useI18n();
  const { can } = useAuth();
  const [f, setF] = useState<Record<string, string>>({});
  const [releasing, setReleasing] = useState(false);
  const [lastError, setLastError] = useState<unknown>(null);
  const { busy, error, run } = useAction();
  useEffect(() => setF({
    ...Object.fromEntries(FIELDS.map((k) => [k, c[k] ?? ""])), risk_level: c.risk_level ?? "",
    customer_notification_required: c.customer_notification_required === null ? "" : String(c.customer_notification_required),
    customer_notified_on: c.customer_notified_on ?? "", responsible_id: c.responsible_id,
  }), [c]);
  const editable = caps.has("investigate") && can("oot:manage");
  const points = (rows: OotCase["as_found"], title: string) => rows && rows.length > 0 && (
    <div><div className="mb-1 text-[11px] font-semibold uppercase text-ink-3">{title}</div>
      <table className="data-table"><thead><tr><th>#</th><th>Nominal</th><th>Lim.</th><th>Measured</th><th /></tr></thead>
        <tbody>{rows.map((p) => <tr key={p.sequence}><td>{p.sequence}</td><td className="tabular">{p.nominal}</td>
          <td className="tabular">{p.lower} … {p.upper} {p.unit}</td><td className="tabular">{p.measured}</td>
          <td>{p.in_tolerance ? <ToneBadge tone="ok">OK</ToneBadge> : <ToneBadge tone="bad">OOT {p.deviation_outside}</ToneBadge>}</td></tr>)}</tbody></table></div>
  );
  return (
    <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
      <div className="space-y-4">
        <Card title={t("common.general")}>
          <div className="grid gap-3 sm:grid-cols-3">
            <Spec label={t("msa.gage")} mono><Link className="text-accent hover:underline" href={`/gages/${c.gage_id}`}>{c.gage_code}</Link> · {c.gage_description}</Spec>
            <Spec label={t("oot.detected")}>{fmtDate(c.detected_on)} · {t(`oot.src.${c.detection_source}` as "oot.src.MANUAL")}</Spec>
            <Spec label={t("msa.responsible")}>{users[c.responsible_id] ?? "—"}</Spec>
            <Spec label={t("oot.deviation")} mono>{c.max_deviation ?? "—"}</Spec>
            <Spec label={t("oot.tolerance")} mono>{c.tolerance ?? "—"}</Spec>
            <Spec label={t("oot.found")}>{c.found_result ?? "—"}</Spec>
          </div>
          <p className="mt-3 whitespace-pre-line text-[13px]">{c.description}</p>
          <div className="mt-3 grid gap-3 md:grid-cols-2">{points(c.as_found, t("oot.asFound"))}{points(c.as_left, t("oot.asLeft"))}</div>
        </Card>
        <Card title={t("oot.investigation")}>
          {error && <Alert>{error}<IssueList error={lastError} /></Alert>}
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label={t("oot.risk")}><Select disabled={!editable} value={f.risk_level ?? ""} onChange={(e) => setF({ ...f, risk_level: e.target.value })}>
              <option value="">—</option>{["LOW", "MEDIUM", "HIGH"].map((r) => <option key={r} value={r}>{t(`oot.risk.${r}` as "oot.risk.LOW")}</option>)}</Select></Field>
            <Field label={t("oot.customerRequired")}><Select disabled={!editable} value={f.customer_notification_required ?? ""}
              onChange={(e) => setF({ ...f, customer_notification_required: e.target.value })}>
              <option value="">—</option><option value="true">{t("common.yes")}</option><option value="false">{t("common.no")}</option></Select></Field>
            <Field label={t("oot.customerNotifiedOn")}><Input type="date" disabled={!editable} value={f.customer_notified_on ?? ""}
              onChange={(e) => setF({ ...f, customer_notified_on: e.target.value })} /></Field>
            <Field label={t("msa.responsible")}><Select disabled={!editable} value={f.responsible_id ?? ""} onChange={(e) => setF({ ...f, responsible_id: e.target.value })}>
              {userList.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}</Select></Field>
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {FIELDS.map((k) => <Field key={k} label={t(LABEL[k] as "oot.scope")}><Textarea rows={3} disabled={!editable} value={f[k] ?? ""}
              onChange={(e) => setF({ ...f, [k]: e.target.value })} /></Field>)}
          </div>
          {editable && <Button className="mt-3" variant="primary" disabled={!!busy} onClick={() => run("save", async () => {
            setLastError(null);
            const body: Record<string, unknown> = Object.fromEntries(FIELDS.map((k) => [k, f[k] || null]));
            body.risk_level = f.risk_level || null;
            body.customer_notification_required = f.customer_notification_required === "" ? null : f.customer_notification_required === "true";
            body.customer_notified_on = f.customer_notified_on || null;
            body.responsible_id = f.responsible_id;
            try { await api.patch(`/oot/cases/${c.id}`, body); } catch (e) { setLastError(e); throw e; }
          }, onChange)}>{t("common.save")}</Button>}
        </Card>
        <CustomFieldsCard entity="oot_case" id={c.id} canEdit={editable} />
        <DocumentsPanel entityType="oot_case" entityId={c.id} canUpload={can("oot:manage")} />
      </div>
      <div className="space-y-4">
        <Card title={t("oot.restriction")}>
          {c.restriction_applied ? (
            c.gage_released_at ? <Alert tone="ok">{t("oot.released", { d: fmtDateTime(c.gage_released_at), r: c.gage_release_reason ?? "" })}</Alert>
              : <Alert tone="bad">{t("oot.restricted", { s: c.gage_prior_control_status ?? "—" })}</Alert>
          ) : <p className="text-[13px] text-ink-3">{t("oot.notRestricted")}</p>}
          {c.restriction_applied && !c.gage_released_at && caps.has("release_gage") && can("oot:approve") && can("gages:release") && (
            <><p className="mt-2 text-[12px] text-ink-3">{t("oot.releaseHelp")}</p>
              <Button className="mt-2" onClick={() => setReleasing(true)}>{t("oot.releaseGage")}</Button></>
          )}
        </Card>
        {!!c.close_gaps.length && c.status !== "CLOSED" && c.status !== "CANCELLED" && (
          <Card title={t("oot.closeGaps")}><ul className="list-disc pl-5 text-[13px]">
            {c.close_gaps.map((g) => <li key={g}>{t(`oot.req.${g}` as "oot.req.disposition")}</li>)}</ul></Card>
        )}
        <WorkflowPanel entity="oot_case" id={c.id} onChange={onChange} users={users} />
      </div>
      <ReasonDialog open={releasing} title={t("oot.releaseGage")} label={t("common.reason")} onClose={() => setReleasing(false)}
        onConfirm={(reason) => run("rel", () => api.post(`/oot/cases/${c.id}/release-gage`, { reason }), () => { setReleasing(false); onChange(); })} />
    </div>
  );
}

function AnalysisTab({ c, caps, onChange }: { c: OotCase; caps: Set<string>; onChange: () => void }) {
  const { t, fmtDate, fmtDateTime } = useI18n();
  const { can } = useAuth();
  const items = useResource(() => api.get<OotItem[]>(`/oot/cases/${c.id}/items`), [c.id, c.analysis_generated_at]);
  const [assess, setAssess] = useState<{ item: OotItem; value: string; note: string } | null>(null);
  const [manual, setManual] = useState<{ ref_code: string; description: string } | null>(null);
  const { busy, error, run } = useAction();
  const editable = caps.has("analyze") && can("oot:manage");
  return (
    <div className="space-y-4">
      {error && <Alert>{error}</Alert>}
      <Card title={t("oot.window")} actions={editable && <Button variant="primary" disabled={!!busy}
        onClick={() => run("gen", () => api.post(`/oot/cases/${c.id}/analysis`), () => { onChange(); items.reload(); })}>{t("oot.analysis")}</Button>}>
        {c.analysis_generated_at ? (
          <div className="grid gap-3 sm:grid-cols-3">
            <Spec label={t("oot.window")}>{fmtDate(c.impact_start)} → {fmtDate(c.impact_end)}</Spec>
            <Spec label={t("oot.lastAcceptable")}>{c.last_acceptable_calibration_id ? <Link className="text-accent hover:underline" href={`/calibrations/${c.last_acceptable_calibration_id}`}>{t("common.view")}</Link> : "—"}</Spec>
            <Spec label="">{fmtDateTime(c.analysis_generated_at)}</Spec>
          </div>
        ) : <p className="text-[13px] text-ink-3">{t("oot.noItems")}</p>}
        {c.limitations && <Alert tone="warn"><b>{t("oot.limitations")}</b><div className="whitespace-pre-line">{c.limitations}</div></Alert>}
      </Card>
      <Card title={`${t("oot.items")} (${items.data?.length ?? 0})`} flush
        actions={editable && <Button onClick={() => setManual({ ref_code: "", description: "" })}>+ {t("oot.addManual")}</Button>}>
        {!items.data?.length ? <EmptyState>{t("oot.noItems")}</EmptyState> : (
          <div className="overflow-x-auto"><table className="data-table">
            <thead><tr><th>{t("cmp.kind")}</th><th>{t("oot.refCode")}</th><th>{t("common.description")}</th><th>{t("common.date")}</th><th>{t("common.status")}</th><th /></tr></thead>
            <tbody>{items.data.map((i) => (
              <tr key={i.id}>
                <td className="text-[12px]">{t(`oot.item.${i.item_type}` as "oot.item.MANUAL")}</td>
                <td className="font-mono text-[12px]">{i.ref_code ?? "—"}</td>
                <td className="max-w-[420px] text-[12px]">{i.description}{i.assessment_note && <div className="text-ink-3">“{i.assessment_note}”</div>}</td>
                <td className="tabular text-[12px]">{fmtDateTime(i.occurred_at)}</td>
                <td><ToneBadge tone={ASSESSMENT_TONE[i.assessment]}>{t(`oot.as.${i.assessment}` as "oot.as.PENDING")}</ToneBadge></td>
                <td>{editable && <Button variant="ghost" onClick={() => setAssess({ item: i, value: i.assessment === "PENDING" ? "NO_IMPACT" : i.assessment, note: i.assessment_note ?? "" })}>{t("oot.assess")}</Button>}</td>
              </tr>))}</tbody></table></div>
        )}
      </Card>
      <Modal open={!!assess} title={t("oot.assess")} onClose={() => setAssess(null)}
        footer={<Button variant="primary" disabled={!!busy} onClick={() => assess && run("as", () => api.post(`/oot/items/${assess.item.id}/assess`,
          { assessment: assess.value, note: assess.note || null }), () => { setAssess(null); items.reload(); onChange(); })}>{t("common.save")}</Button>}>
        {error && <Alert>{error}</Alert>}
        {assess && <>
          <Field label={t("common.status")}><Select value={assess.value} onChange={(e) => setAssess({ ...assess, value: e.target.value })}>
            {["NO_IMPACT", "IMPACT", "REINSPECT", "PENDING"].map((a) => <option key={a} value={a}>{t(`oot.as.${a}` as "oot.as.PENDING")}</option>)}</Select></Field>
          <Field label={t("wf.comment")} className="mt-3"><Textarea value={assess.note} onChange={(e) => setAssess({ ...assess, note: e.target.value })} /></Field>
        </>}
      </Modal>
      <Modal open={!!manual} title={t("oot.addManual")} onClose={() => setManual(null)}
        footer={<Button variant="primary" disabled={!manual?.description.trim() || !!busy} onClick={() => manual && run("m", () => api.post(`/oot/cases/${c.id}/items`,
          { ref_code: manual.ref_code || null, description: manual.description }), () => { setManual(null); items.reload(); })}>{t("common.save")}</Button>}>
        {manual && <>
          <Field label={t("oot.refCode")}><Input value={manual.ref_code} onChange={(e) => setManual({ ...manual, ref_code: e.target.value })} /></Field>
          <Field label={t("common.description")} required className="mt-3"><Textarea value={manual.description} onChange={(e) => setManual({ ...manual, description: e.target.value })} /></Field>
        </>}
      </Modal>
    </div>
  );
}

function ActionsTab({ c, caps, users, userList }: { c: OotCase; caps: Set<string>; users: Record<string, string>; userList: { id: string; full_name: string }[] }) {
  const { t, fmtDate } = useI18n();
  const { can, me } = useAuth();
  const actions = useResource(() => api.get<OotAction[]>(`/oot/cases/${c.id}/actions`), [c.id]);
  const [form, setForm] = useState<Record<string, string> | null>(null);
  const [finishing, setFinishing] = useState<OotAction | null>(null);
  const { busy, error, run } = useAction();
  const editable = caps.has("act") && can("oot:manage");
  return (
    <Card title={t("oot.tab.actions")} flush actions={editable && <Button variant="primary" onClick={() => setForm({ action_type: "CONTAINMENT", owner_id: me?.id ?? "" })}>+ {t("oot.addAction")}</Button>}>
      {error && <div className="p-3"><Alert>{error}</Alert></div>}
      {!actions.data?.length ? <EmptyState>—</EmptyState> : (
        <table className="data-table"><thead><tr><th>{t("oot.actionType")}</th><th>{t("common.description")}</th><th>{t("oot.owner")}</th><th>{t("oot.due")}</th><th>{t("common.status")}</th><th /></tr></thead>
          <tbody>{actions.data.map((a) => <tr key={a.id}>
            <td className="text-[12px]">{t(`oot.act.${a.action_type}` as "oot.act.OTHER")}</td><td className="text-[12px]">{a.description}{a.result_note && <div className="text-ink-3">→ {a.result_note}</div>}</td>
            <td className="text-[12px]">{users[a.owner_id] ?? "—"}</td><td className="tabular">{fmtDate(a.due_date)}</td>
            <td><ToneBadge tone={a.status === "DONE" ? "ok" : a.status === "OPEN" ? "warn" : "mute"}>{a.status}</ToneBadge></td>
            <td>{a.status === "OPEN" && caps.has("act") && (a.owner_id === me?.id || can("oot:approve")) && <Button variant="ghost" onClick={() => setFinishing(a)}>{t("oot.finish")}</Button>}</td>
          </tr>)}</tbody></table>
      )}
      <Modal open={!!form} title={t("oot.addAction")} onClose={() => setForm(null)}
        footer={<Button variant="primary" disabled={!form?.description || !!busy} onClick={() => form && run("add", () => api.post(`/oot/cases/${c.id}/actions`,
          { ...form, due_date: form.due_date || null }), () => { setForm(null); actions.reload(); })}>{t("common.save")}</Button>}>
        {form && <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("oot.actionType")}><Select value={form.action_type} onChange={(e) => setForm({ ...form, action_type: e.target.value })}>
            {["CONTAINMENT", "REINSPECTION", "CORRECTIVE", "CUSTOMER_NOTIFICATION", "OTHER"].map((a) => <option key={a} value={a}>{t(`oot.act.${a}` as "oot.act.OTHER")}</option>)}</Select></Field>
          <Field label={t("oot.owner")}><Select value={form.owner_id} onChange={(e) => setForm({ ...form, owner_id: e.target.value })}>
            {userList.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}</Select></Field>
          <Field label={t("oot.due")}><Input type="date" value={form.due_date ?? ""} onChange={(e) => setForm({ ...form, due_date: e.target.value })} /></Field>
          <Field label={t("common.description")} required className="sm:col-span-2"><Textarea value={form.description ?? ""} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
        </div>}
      </Modal>
      <ReasonDialog open={!!finishing} title={t("oot.finish")} label={t("oot.resultNote")} onClose={() => setFinishing(null)}
        onConfirm={(note) => run("fin", () => api.post(`/oot/actions/${finishing!.id}/finish`, { done: true, note }), () => { setFinishing(null); actions.reload(); })} />
    </Card>
  );
}

function CalTab({ id }: { id: string }) {
  const { t, fmtDate } = useI18n();
  const rows = useResource(() => api.get<CalHistoryRow[]>(`/oot/cases/${id}/calibration-history`), [id]);
  if (rows.error) return <ErrorState error={rows.error} />;
  if (!rows.data) return <Loading />;
  return (
    <Card flush title={t("oot.tab.calibrations")}>
      <table className="data-table"><thead><tr><th>{t("msa.code")}</th><th>{t("common.type")}</th><th>{t("common.date")}</th><th>{t("common.status")}</th><th>{t("common.result")}</th><th>As Found</th><th>As Left</th><th /></tr></thead>
        <tbody>{rows.data.map((r) => <tr key={r.id}>
          <td><Link href={`/calibrations/${r.id}`} className="font-mono text-[12px] text-accent hover:underline">{r.calibration_code}</Link></td>
          <td className="text-[12px]">{r.activity_type}</td><td className="tabular">{fmtDate(r.performed_date)}</td><td className="text-[12px]">{r.status}</td>
          <td className="text-[12px]">{r.result ?? "—"}</td>
          <td>{r.as_found_in_tolerance === null ? "—" : r.as_found_in_tolerance ? "OK" : <ToneBadge tone="bad">OOT</ToneBadge>}</td>
          <td>{r.as_left_in_tolerance === null ? "—" : r.as_left_in_tolerance ? "OK" : <ToneBadge tone="bad">OOT</ToneBadge>}</td>
          <td className="text-[11px]">{r.is_detection && <ToneBadge tone="bad">{t("oot.detected")}</ToneBadge>}{r.is_last_acceptable && <ToneBadge tone="ok">{t("oot.lastAcceptable")}</ToneBadge>}</td>
        </tr>)}</tbody></table>
    </Card>
  );
}
