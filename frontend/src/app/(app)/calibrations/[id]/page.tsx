"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { DocumentsPanel } from "@/components/documents";
import { Icon } from "@/components/icons";
import {
  Alert, Button, Card, Check, ErrorState, Field, FileInput, Input, Loading, PageHeader, ReasonDialog, Section, Select,
  Spec, Textarea, ToneBadge, cx, useAction,
} from "@/components/ui";
import { api, form } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import type { MessageKey } from "@/lib/messages";
import { CAL_RESULT_TONE, CAL_STATUS_TONE, STD_STATUS_TONE } from "@/lib/status";
import type { ActivityDetail, CalPoint, Standard } from "@/lib/types";

const STEPS = ["PLANNED", "REQUESTED", "SCHEDULED", "IN_PROGRESS", "PENDING_REVIEW", "PENDING_APPROVAL", "APPROVED", "RELEASED"];
const AUTH_ACTIVITY: Record<string, string | undefined> = {
  INTERNAL_CALIBRATION: "INTERNAL_CALIBRATION", ROUTINE_VERIFICATION: "ROUTINE_VERIFICATION",
};

export default function CalibrationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { t, fmtDate, fmtDateTime } = useI18n();
  const { can } = useAuth();
  const act = useResource(() => api.get<ActivityDetail>(`/calibrations/${id}`), [id]);
  const { busy, error, run } = useAction();
  const [dialog, setDialog] = useState<null | "cancel" | "return" | "reject">(null);

  if (act.error) return <ErrorState error={act.error} onRetry={act.reload} />;
  if (!act.data) return <Loading />;
  const a = act.data;
  const post = (path: string, body: unknown = {}) => () => api.post<ActivityDetail>(`/calibrations/${a.id}/${path}`, body);
  const step = STEPS.indexOf(a.status);
  const cancellable = ["PLANNED", "REQUESTED", "SCHEDULED", "IN_PROGRESS", "PENDING_REVIEW", "PENDING_APPROVAL"].includes(a.status);

  return (
    <>
      <Link href="/calibrations" className="mb-3 inline-flex items-center gap-1 text-[12px] text-ink-3 hover:text-ink">
        <Icon name="back" size={14} /> {t("cal.title")}
      </Link>
      <PageHeader
        eyebrow={t(`cal.type.${a.activity_type}`)}
        title={<span className="flex flex-wrap items-center gap-3"><span className="font-mono">{a.calibration_code}</span>
          <ToneBadge tone={CAL_STATUS_TONE[a.status]}>{t(`cal.status.${a.status}`)}</ToneBadge></span>}
        actions={cancellable && can("calibration:manage") && (
          <Button variant="danger" onClick={() => setDialog("cancel")}>{t("cal.action.cancel")}</Button>
        )}
      >
        <p className="mt-1 text-[14px] text-ink-2">
          <Link href={`/gages/${a.gage_id}`} className="font-mono font-semibold text-accent hover:underline">{a.gage_code}</Link> · {a.gage_description}
        </p>
      </PageHeader>

      {a.status !== "CANCELLED" && (
        <ol className="mb-5 grid grid-cols-4 gap-1 md:grid-cols-8" aria-label="workflow">
          {STEPS.map((s, i) => (
            <li key={s} className={cx("rounded px-2 py-1.5 text-center text-[11px] font-medium",
              i < step ? "bg-ok-soft text-ok" : i === step ? "bg-accent text-white" : "bg-line-2 text-ink-3")}>
              {t(`cal.status.${s}` as MessageKey)}
            </li>
          ))}
        </ol>
      )}
      {a.status === "CANCELLED" && <div className="mb-4"><Alert tone="warn">{a.cancel_reason}</Alert></div>}
      {error && <div className="mb-4"><Alert>{error}</Alert></div>}

      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <div className="min-w-0 space-y-4">
          <Planning a={a} onChange={act.reload} />
          {["IN_PROGRESS", "PENDING_REVIEW", "PENDING_APPROVAL", "APPROVED", "RELEASED"].includes(a.status) && (
            <>
              <Execution a={a} onChange={act.reload} />
              <Points a={a} onChange={act.reload} />
              <Standards a={a} onChange={act.reload} />
              <Certificates a={a} onChange={act.reload} />
              <DocumentsPanel entityType="calibration" entityId={a.id} title={t("doc.EVIDENCE")}
                canUpload={can("calibration:execute") && a.status === "IN_PROGRESS"} />
            </>
          )}
        </div>

        <div className="space-y-4">
          <Card title={t("common.result")}>
            <div className="space-y-3">
              {(a.result ?? a.computed_result) ? (
                <ToneBadge tone={CAL_RESULT_TONE[(a.result ?? a.computed_result)!]}>
                  {t(`cal.result.${(a.result ?? a.computed_result)!}`)}
                </ToneBadge>
              ) : <span className="text-[13px] text-ink-3">—</span>}
              {a.as_found_in_tolerance === false && a.result !== "FAIL" && <Alert tone="warn">{t("cal.asFoundOot")}</Alert>}
              <dl className="grid grid-cols-2 gap-3">
                <Spec label={t("cal.performed")} mono>{fmtDate(a.performed_date)}</Spec>
                <Spec label={t("cal.dueDate")} mono>{fmtDate(a.due_date)}</Spec>
                <Spec label={t("cal.reviewer")}>{a.reviewer_name}</Spec>
                <Spec label={t("cal.approver")}>{a.approver_name}</Spec>
                <Spec label={t("cal.releasedAt")}>{a.released_at ? fmtDateTime(a.released_at) : null}</Spec>
                <Spec label={t("cal.technician")}>{a.technician_name}</Spec>
              </dl>
              {a.review_comments && <p className="text-[12px] text-ink-2">“{a.review_comments}”</p>}
            </div>
            {/* Workflow actions */}
            <div className="mt-4 flex flex-col gap-2 border-t border-line pt-4">
              {a.status === "IN_PROGRESS" && can("calibration:execute") && (
                <>
                  {a.missing_requirements.length > 0 && (
                    <Alert tone="warn">
                      <div className="font-medium">{t("cal.missing")}</div>
                      <ul className="mt-1 list-inside list-disc">
                        {a.missing_requirements.map((m) => <li key={m}>{t(`cal.missing.${m}` as MessageKey)}</li>)}
                      </ul>
                    </Alert>
                  )}
                  <Button variant="primary" disabled={a.missing_requirements.length > 0} loading={busy === "submit"}
                    onClick={() => run("submit", post("submit"), act.reload)}>{t("cal.action.submit")}</Button>
                </>
              )}
              {a.status === "PENDING_REVIEW" && can("calibration:review") && (
                <>
                  <Button variant="primary" loading={busy === "review"} onClick={() => run("review", post("review", { accept: true }), act.reload)}>
                    {t("cal.action.reviewOk")}
                  </Button>
                  <Button onClick={() => setDialog("return")}>{t("cal.action.reviewReturn")}</Button>
                </>
              )}
              {a.status === "PENDING_APPROVAL" && can("calibration:approve") && (
                <>
                  <Button variant="primary" loading={busy === "approve"} onClick={() => run("approve", post("approve", { accept: true }), act.reload)}>
                    {t("cal.action.approve")}
                  </Button>
                  <Button onClick={() => setDialog("reject")}>{t("cal.action.reject")}</Button>
                </>
              )}
              {a.status === "APPROVED" && can("calibration:release") && (
                <>
                  <p className="text-[12px] text-ink-3">{t("cal.releaseNote")}</p>
                  <Button variant="primary" loading={busy === "release"} onClick={() => run("release", post("release"), act.reload)}>
                    {t("cal.action.release")}
                  </Button>
                </>
              )}
            </div>
          </Card>

          <Card title={t("cal.requirements")}>
            <ul className="space-y-1 text-[13px]">
              {(["require_certificate", "require_standard", "require_as_found", "require_environment"] as const).map((k) => (
                <li key={k} className="flex items-center justify-between">
                  <span className="text-ink-2">{t(`cal.req.${k}`)}</span>
                  <span className={a.requirements[k] ? "font-semibold text-ink" : "text-ink-3"}>{a.requirements[k] ? t("common.yes") : t("common.no")}</span>
                </li>
              ))}
            </ul>
          </Card>

          <Card flush title={t("common.history")}>
            <ol className="px-4 py-3">
              {a.history.map((h) => (
                <li key={h.id} className="border-l-2 border-line pb-3 pl-3 last:pb-0">
                  <div className="text-[12px] font-medium">
                    {h.from_status ? `${t(`cal.status.${h.from_status}` as MessageKey)} → ` : ""}{t(`cal.status.${h.to_status}` as MessageKey)}
                  </div>
                  {h.comment && <p className="text-[12px] text-ink-2">“{h.comment}”</p>}
                  <p className="text-[11px] text-ink-3">{h.changed_by_name} · {fmtDateTime(h.changed_at)}</p>
                </li>
              ))}
            </ol>
          </Card>
        </div>
      </div>

      <ReasonDialog open={dialog === "cancel"} title={t("cal.action.cancel")} label={t("common.reasonRequired")} danger
        onClose={() => setDialog(null)} onConfirm={(reason) => api.post(`/calibrations/${a.id}/cancel`, { reason }).then(act.reload)} />
      <ReasonDialog open={dialog === "return"} title={t("cal.action.reviewReturn")} label={t("common.reasonRequired")}
        onClose={() => setDialog(null)} onConfirm={(c) => api.post(`/calibrations/${a.id}/review`, { accept: false, comments: c }).then(act.reload)} />
      <ReasonDialog open={dialog === "reject"} title={t("cal.action.reject")} label={t("common.reasonRequired")}
        onClose={() => setDialog(null)} onConfirm={(c) => api.post(`/calibrations/${a.id}/approve`, { accept: false, comments: c }).then(act.reload)} />
    </>
  );
}

function Planning({ a, onChange }: { a: ActivityDetail; onChange: () => void }) {
  const { t, fmtDate } = useI18n();
  const { can } = useAuth();
  const { busy, error, run } = useAction();
  const authActivity = AUTH_ACTIVITY[a.activity_type];
  const techs = useResource(
    () => (authActivity && can("competency:read")
      ? api.get<{ id: string; full_name: string }[]>("/competency/authorized-users", { activity: authActivity })
      : Promise.resolve([])),
    [a.activity_type],
  );
  const [f, setF] = useState({ scheduled_date: "", technician_id: "", provider_name: "", provider_accreditation: "" });
  useEffect(() => setF({ scheduled_date: a.scheduled_date ?? a.planned_date, technician_id: a.technician_id ?? "",
    provider_name: a.provider_name ?? "", provider_accreditation: a.provider_accreditation ?? "" }), [a]);
  const external = a.activity_type === "EXTERNAL_CALIBRATION";

  return (
    <Card title={t("cal.planned")}>
      {error && <div className="mb-3"><Alert>{error}</Alert></div>}
      <dl className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Spec label={t("cal.planned")} mono>{fmtDate(a.planned_date)}</Spec>
        <Spec label={t("cal.scheduled")} mono>{fmtDate(a.scheduled_date)}</Spec>
        <Spec label={external ? t("cal.provider") : t("cal.technician")}>{external ? a.provider_name : a.technician_name}</Spec>
        <Spec label={t("cal.accreditation")}>{a.provider_accreditation}</Spec>
      </dl>
      {can("calibration:manage") && a.status === "PLANNED" && (
        <div className="mt-4 border-t border-line pt-4">
          <Button variant="primary" loading={busy === "req"} onClick={() => run("req", () => api.post(`/calibrations/${a.id}/request`, {}), onChange)}>
            {t("cal.action.request")}
          </Button>
        </div>
      )}
      {can("calibration:manage") && ["REQUESTED", "SCHEDULED"].includes(a.status) && (
        <div className="mt-4 grid gap-3 border-t border-line pt-4 sm:grid-cols-2 lg:grid-cols-4 lg:items-end">
          <Field label={t("cal.scheduled")} required>
            <Input type="date" className="font-mono" value={f.scheduled_date} onChange={(e) => setF({ ...f, scheduled_date: e.target.value })} />
          </Field>
          {external ? (
            <>
              <Field label={t("cal.provider")} required>
                <Input value={f.provider_name} onChange={(e) => setF({ ...f, provider_name: e.target.value })} />
              </Field>
              <Field label={t("cal.accreditation")}>
                <Input value={f.provider_accreditation} onChange={(e) => setF({ ...f, provider_accreditation: e.target.value })} />
              </Field>
            </>
          ) : (
            <Field label={t("cal.technician")} required hint={techs.data?.length === 0 ? t("comp.auth.grant") : undefined}>
              <Select value={f.technician_id} onChange={(e) => setF({ ...f, technician_id: e.target.value })}>
                <option value="" />
                {techs.data?.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
              </Select>
            </Field>
          )}
          <Button variant="primary" loading={busy === "sch"} onClick={() => run("sch", () => api.post(`/calibrations/${a.id}/schedule`, {
            scheduled_date: f.scheduled_date, technician_id: f.technician_id || null, provider_name: f.provider_name || null,
            provider_accreditation: f.provider_accreditation || null,
          }), onChange)}>{t("cal.action.schedule")}</Button>
        </div>
      )}
      {can("calibration:execute") && a.status === "SCHEDULED" && (
        <div className="mt-4 border-t border-line pt-4">
          <Button variant="primary" loading={busy === "start"} onClick={() => run("start", () => api.post(`/calibrations/${a.id}/start`), onChange)}>
            {t("cal.action.start")}
          </Button>
        </div>
      )}
    </Card>
  );
}

function Execution({ a, onChange }: { a: ActivityDetail; onChange: () => void }) {
  const { t, fmtDate } = useI18n();
  const { can } = useAuth();
  const editable = a.status === "IN_PROGRESS" && can("calibration:execute");
  const { busy, error, run } = useAction();
  const init = () => ({
    performed_date: a.performed_date ?? "", method: a.method ?? "", environment_temperature: a.environment_temperature ?? "",
    environment_humidity: a.environment_humidity ?? "", environment_notes: a.environment_notes ?? "",
    uncertainty: a.uncertainty ?? "", adjusted: a.adjusted, declared_result: a.declared_result ?? "",
    observations: a.observations ?? "",
  });
  const [f, setF] = useState(init);
  useEffect(() => setF(init()), [a]); // eslint-disable-line react-hooks/exhaustive-deps
  const s = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });
  const hasPoints = a.points.some((p) => !p.superseded);

  if (!editable) {
    return (
      <Card title={t("cal.environment")}>
        <dl className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Spec label={t("cal.performed")} mono>{fmtDate(a.performed_date)}</Spec>
          <Spec label={t("cal.method")}>{a.method}</Spec>
          <Spec label={t("cal.temperature")} mono>{a.environment_temperature}</Spec>
          <Spec label={t("cal.humidity")} mono>{a.environment_humidity}</Spec>
          <Spec label={t("cal.uncertainty")} mono>{a.uncertainty}</Spec>
          <Spec label={t("cal.adjusted")}>{a.adjusted ? t("common.yes") : t("common.no")}</Spec>
          <Spec label={t("cal.provider")}>{a.provider_name}</Spec>
        </dl>
        {a.observations && <p className="mt-3 whitespace-pre-wrap border-t border-line pt-3 text-[13px] text-ink-2">{a.observations}</p>}
      </Card>
    );
  }
  return (
    <Card title={t("cal.environment")}>
      {error && <div className="mb-3"><Alert>{error}</Alert></div>}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Field label={t("cal.performed")}><Input type="date" className="font-mono" value={f.performed_date} onChange={s("performed_date")} /></Field>
        <Field label={t("cal.method")} className="lg:col-span-3"><Input maxLength={300} value={f.method} onChange={s("method")} /></Field>
        <Field label={t("cal.temperature")}><Input inputMode="decimal" className="font-mono" value={f.environment_temperature} onChange={s("environment_temperature")} /></Field>
        <Field label={t("cal.humidity")}><Input inputMode="decimal" className="font-mono" value={f.environment_humidity} onChange={s("environment_humidity")} /></Field>
        <Field label={t("cal.envNotes")}><Input maxLength={300} value={f.environment_notes} onChange={s("environment_notes")} /></Field>
        <Field label={t("cal.uncertainty")}><Input maxLength={200} value={f.uncertainty} onChange={s("uncertainty")} /></Field>
        {!hasPoints && (
          <Field label={t("cal.declaredResult")} className="sm:col-span-2">
            <Select value={f.declared_result} onChange={s("declared_result")}>
              <option value="">—</option>
              {(["PASS", "PASS_AFTER_ADJUSTMENT", "FAIL"] as const).map((r) => <option key={r} value={r}>{t(`cal.result.${r}`)}</option>)}
            </Select>
          </Field>
        )}
        <div className="flex items-end pb-2"><Check label={t("cal.adjusted")} checked={f.adjusted} onChange={(v) => setF({ ...f, adjusted: v })} /></div>
      </div>
      <Field label={t("common.notes")} className="mt-3"><Textarea maxLength={4000} value={f.observations} onChange={s("observations")} /></Field>
      <div className="mt-3 flex justify-end">
        <Button variant="primary" loading={busy === "save"} onClick={() => run("save", () => api.patch(`/calibrations/${a.id}`, {
          performed_date: f.performed_date || null, method: f.method || null,
          environment_temperature: f.environment_temperature || null, environment_humidity: f.environment_humidity || null,
          environment_notes: f.environment_notes || null, uncertainty: f.uncertainty || null, adjusted: f.adjusted,
          declared_result: f.declared_result || null, observations: f.observations || null,
        }), onChange)}>{t("cal.action.save")}</Button>
      </div>
    </Card>
  );
}

function Points({ a, onChange }: { a: ActivityDetail; onChange: () => void }) {
  const { t } = useI18n();
  const { can } = useAuth();
  const editable = a.status === "IN_PROGRESS" && can("calibration:execute");
  const [correcting, setCorrecting] = useState<CalPoint | null>(null);
  return (
    <Card title={`${t("cal.asFound")} / ${t("cal.asLeft")}`}>
      <div className="space-y-5">
        {(["AS_FOUND", "AS_LEFT"] as const).map((phase) => (
          <Section key={phase} title={`${phase === "AS_FOUND" ? t("cal.asFound") : t("cal.asLeft")} — ${phase === "AS_FOUND" ? t("cal.asFoundHint") : t("cal.asLeftHint")}`}>
            <PointTable points={a.points.filter((p) => p.phase === phase)} onCorrect={editable ? setCorrecting : undefined} />
            {editable && (phase === "AS_FOUND" || a.adjusted) && <PointForm activityId={a.id} phase={phase} onDone={onChange} />}
          </Section>
        ))}
      </div>
      {correcting && (
        <CorrectionDialog point={correcting} activityId={a.id} onClose={() => setCorrecting(null)} onDone={() => { setCorrecting(null); onChange(); }} />
      )}
    </Card>
  );
}

function PointTable({ points, onCorrect }: { points: CalPoint[]; onCorrect?: (p: CalPoint) => void }) {
  const { t } = useI18n();
  if (!points.length) return <p className="text-[13px] text-ink-3">{t("cal.point.empty")}</p>;
  return (
    <div className="overflow-x-auto rounded border border-line">
      <table className="data-table">
        <thead><tr><th>#</th><th>{t("common.description")}</th><th>{t("cal.point.nominal")}</th><th>{t("cal.point.lower")}</th>
          <th>{t("cal.point.upper")}</th><th>{t("cal.point.measured")}</th><th>{t("common.result")}</th><th /></tr></thead>
        <tbody>
          {points.map((p) => (
            <tr key={p.id} className={p.superseded ? "text-ink-3 line-through" : ""}>
              <td className="tabular">{p.sequence}</td>
              <td className="max-w-[180px] truncate">{p.description ?? "—"}{p.correction_reason && <div className="text-[11px] no-underline text-ink-3">↺ {p.correction_reason}</div>}</td>
              <td className="font-mono tabular">{p.nominal}</td>
              <td className="font-mono tabular">{p.lower_limit}</td>
              <td className="font-mono tabular">{p.upper_limit}</td>
              <td className="font-mono tabular font-semibold">{p.measured} {p.unit ?? ""}</td>
              <td>{p.superseded ? <span className="text-[11px]">{t("cal.point.superseded")}</span>
                : <ToneBadge tone={p.in_tolerance ? "ok" : "bad"}>{p.in_tolerance ? "OK" : "NOK"}</ToneBadge>}</td>
              <td>{onCorrect && !p.superseded && <Button variant="ghost" className="h-7 px-2" onClick={() => onCorrect(p)}>{t("cal.point.correct")}</Button>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PointForm({ activityId, phase, onDone }: { activityId: string; phase: "AS_FOUND" | "AS_LEFT"; onDone: () => void }) {
  const { t } = useI18n();
  const { busy, error, run } = useAction();
  const empty = { description: "", nominal: "", lower_limit: "", upper_limit: "", measured: "", unit: "" };
  const [f, setF] = useState(empty);
  const s = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });
  const ready = f.nominal && f.lower_limit && f.upper_limit && f.measured;
  return (
    <div className="mt-2">
      {error && <Alert>{error}</Alert>}
      <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-7">
        <Input placeholder={t("common.description")} value={f.description} onChange={s("description")} className="sm:col-span-2" />
        <Input placeholder={t("cal.point.nominal")} inputMode="decimal" className="font-mono" value={f.nominal} onChange={s("nominal")} />
        <Input placeholder={t("cal.point.lower")} inputMode="decimal" className="font-mono" value={f.lower_limit} onChange={s("lower_limit")} />
        <Input placeholder={t("cal.point.upper")} inputMode="decimal" className="font-mono" value={f.upper_limit} onChange={s("upper_limit")} />
        <Input placeholder={t("cal.point.measured")} inputMode="decimal" className="font-mono" value={f.measured} onChange={s("measured")} />
        <div className="flex gap-2">
          <Input placeholder="mm" value={f.unit} onChange={s("unit")} className="w-16" />
          <Button variant="primary" disabled={!ready} loading={busy === "p"} onClick={() => run("p", () => api.post(`/calibrations/${activityId}/points`, {
            phase, ...f, description: f.description || null, unit: f.unit || null,
          }), () => { setF({ ...empty, unit: f.unit, lower_limit: "", upper_limit: "" }); onDone(); })}>+</Button>
        </div>
      </div>
    </div>
  );
}

function CorrectionDialog({ point, activityId, onClose, onDone }: { point: CalPoint; activityId: string; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const [measured, setMeasured] = useState(point.measured);
  return (
    <ReasonDialog open title={`${t("cal.point.correction")} · #${point.sequence}`} label={t("common.reasonRequired")}
      onClose={onClose}
      onConfirm={(reason) => api.post(`/calibrations/${activityId}/points`, {
        phase: point.phase, description: point.description, nominal: point.nominal, lower_limit: point.lower_limit,
        upper_limit: point.upper_limit, measured, unit: point.unit, supersedes_id: point.id, correction_reason: reason,
      }).then(onDone)}>
      <Field label={t("cal.point.measured")}>
        <Input inputMode="decimal" className="font-mono" value={measured} onChange={(e) => setMeasured(e.target.value)} />
      </Field>
    </ReasonDialog>
  );
}

function Standards({ a, onChange }: { a: ActivityDetail; onChange: () => void }) {
  const { t, fmtDate } = useI18n();
  const { can } = useAuth();
  const editable = a.status === "IN_PROGRESS" && can("calibration:execute");
  const list = useResource(() => (editable ? api.get<Standard[]>("/standards") : Promise.resolve([])), [editable]);
  const [sid, setSid] = useState("");
  const [exception, setException] = useState("");
  const { busy, error, run } = useAction();
  const selected = list.data?.find((s) => s.id === sid);
  return (
    <Card flush title={t("cal.standards")}>
      {error && <div className="px-4 pt-3"><Alert>{error}</Alert></div>}
      {a.standards.length === 0 ? <p className="px-4 py-4 text-[13px] text-ink-3">{t("cal.standards.empty")}</p> : (
        <ul className="divide-y divide-line-2">
          {a.standards.map((u) => (
            <li key={u.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
              <Link href={`/standards/${u.standard_id}`} className="font-mono text-[13px] font-semibold text-accent hover:underline">{u.standard_code}</Link>
              <span className="min-w-0 flex-1 truncate text-[12px] text-ink-2">{u.standard_description}</span>
              <span className="text-[12px] text-ink-3">{t("std.validUntil")} {fmtDate(u.valid_until)}</span>
              <ToneBadge tone={STD_STATUS_TONE[u.standard_status]}>{t(`std.status.${u.standard_status}` as MessageKey)}</ToneBadge>
              {u.is_exception && <span className="w-full text-[12px] text-warn">⚠ {u.exception_reason}</span>}
            </li>
          ))}
        </ul>
      )}
      {editable && (
        <div className="grid gap-2 border-t border-line bg-line-2/40 px-4 py-3 sm:grid-cols-[1fr_1fr_auto] sm:items-start">
          <Select value={sid} onChange={(e) => setSid(e.target.value)} aria-label={t("std.title")}>
            <option value="" />
            {list.data?.filter((s) => s.control_status !== "INACTIVE").map((s) => (
              <option key={s.id} value={s.id}>{s.standard_code} — {s.description} ({t(`std.status.${s.status}`)})</option>
            ))}
          </Select>
          {selected && !selected.usable ? (
            <Input placeholder={t("cal.standards.exception")} value={exception} onChange={(e) => setException(e.target.value)} />
          ) : <span />}
          <Button variant="primary" disabled={!sid} loading={busy === "s"} onClick={() => run("s", () => api.post(`/calibrations/${a.id}/standards`, {
            standard_id: sid, exception_reason: selected && !selected.usable ? exception || null : null,
          }), () => { setSid(""); setException(""); onChange(); })}>{t("cal.standards.add")}</Button>
        </div>
      )}
    </Card>
  );
}

function Certificates({ a, onChange }: { a: ActivityDetail; onChange: () => void }) {
  const { t, fmtDate } = useI18n();
  const { can } = useAuth();
  const approved = ["APPROVED", "RELEASED"].includes(a.status);
  const canAdd = (a.status === "IN_PROGRESS" && can("calibration:execute")) || (approved && can("calibration:release"));
  const [f, setF] = useState({ certificate_number: "", issuer: a.provider_name ?? "", issue_date: "", replace_reason: "" });
  const [file, setFile] = useState<File | null>(null);
  const [key, setKey] = useState(0);
  const { busy, error, run } = useAction();
  return (
    <Card flush title={t("cal.certificates")}>
      {error && <div className="px-4 pt-3"><Alert>{error}</Alert></div>}
      {a.certificates.length === 0 ? <p className="px-4 py-4 text-[13px] text-ink-3">{t("cal.certificate.empty")}</p> : (
        <ul className="divide-y divide-line-2">
          {a.certificates.map((c) => (
            <li key={c.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
              <span className="font-mono text-[13px] font-semibold">{c.certificate_number}</span>
              <span className="text-[12px] text-ink-2">{c.issuer} · {fmtDate(c.issue_date)}</span>
              <ToneBadge tone={c.status === "CURRENT" ? "ok" : "mute"}>{c.status}</ToneBadge>
              {c.superseded_reason && <span className="text-[11px] text-ink-3">↺ {c.superseded_reason}</span>}
              <Button variant="ghost" className="ml-auto h-7 px-2" onClick={() => api.download(`/attachments/${c.attachment_id}/download`, undefined, { open: true })}>
                {t("common.open")}
              </Button>
            </li>
          ))}
        </ul>
      )}
      {canAdd && (
        <div className="grid gap-2 border-t border-line bg-line-2/40 px-4 py-3 sm:grid-cols-4">
          <Input placeholder={t("cal.certificate.number")} value={f.certificate_number} onChange={(e) => setF({ ...f, certificate_number: e.target.value })} />
          <Input placeholder={t("cal.certificate.issuer")} value={f.issuer} onChange={(e) => setF({ ...f, issuer: e.target.value })} />
          <Input type="date" aria-label={t("cal.certificate.issueDate")} className="font-mono" value={f.issue_date} onChange={(e) => setF({ ...f, issue_date: e.target.value })} />
          <FileInput key={key} accept=".pdf" onFile={setFile} label="PDF" />
          {approved && (
            <Input className="sm:col-span-3" placeholder={t("cal.certificate.replaceReason")} value={f.replace_reason} onChange={(e) => setF({ ...f, replace_reason: e.target.value })} />
          )}
          <Button variant="primary" className={approved ? "" : "sm:col-start-4"} disabled={!file || !f.certificate_number || !f.issuer || !f.issue_date}
            loading={busy === "c"} onClick={() => run("c", () => api.post(`/calibrations/${a.id}/certificates`, form({ ...f, file })),
              () => { setFile(null); setKey((k) => k + 1); setF({ ...f, certificate_number: "", replace_reason: "" }); onChange(); })}>
            {t("common.upload")}
          </Button>
        </div>
      )}
    </Card>
  );
}
