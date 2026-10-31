"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { CustomFieldsCard } from "@/components/custom-fields";
import { DocumentsPanel } from "@/components/documents";
import { MsaCharts } from "@/components/msa-charts";
import { DesignFields, designPayload, designState, type Strs } from "@/components/msa-design";
import {
  Alert, Button, Card, Check, EmptyState, ErrorState, Field, FileInput, Input, Loading, Modal, PageHeader, Select, Spec,
  Tabs, Textarea, ToneBadge, useAction,
} from "@/components/ui";
import { IssueList, WorkflowPanel } from "@/components/workflow";
import { api, form } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { useUsers } from "@/lib/lookups";
import { DECISION_TONE } from "@/lib/status-b3";
import {
  FAMILY, OBS_FIELDS, type CriteriaSet, type Decision, type ImportJob, type MsaObservation, type MsaReport, type MsaResults,
  type MsaRun, type MsaStudy, type RunSummary, type WorkflowState,
} from "@/lib/types-b3";

type Tab = "summary" | "data" | "results" | "reports";

export default function MsaStudyPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useI18n();
  const { can } = useAuth();
  const [tab, setTab] = useState<Tab>("summary");
  const study = useResource(() => api.get<MsaStudy>(`/msa/studies/${id}`), [id]);
  const wf = useResource(() => api.get<WorkflowState>(`/workflows/msa_study/${id}`), [id]);
  const users = useUsers();
  if (study.error) return <ErrorState error={study.error} onRetry={study.reload} />;
  if (!study.data || !wf.data) return <Loading />;
  const s = study.data;
  const caps = new Set(wf.data.capabilities);
  const refresh = () => { study.reload(); wf.reload(); };
  return (
    <>
      <PageHeader eyebrow={t(`msa.m.${s.method}`)} title={`${s.study_code} · ${s.title}`}
        actions={s.final_decision && <ToneBadge tone={DECISION_TONE[s.final_decision]}>{t(`msa.dec.${s.final_decision}`)}</ToneBadge>} />
      <Tabs value={tab} onChange={setTab} items={[
        { value: "summary", label: t("msa.tab.summary") }, { value: "data", label: t("msa.tab.data") },
        { value: "results", label: t("msa.tab.results") }, { value: "reports", label: t("msa.tab.reports") },
      ]} />
      <div className="mt-4 space-y-4">
        {tab === "summary" && <Summary s={s} caps={caps} users={users.names} onChange={refresh} />}
        {tab === "data" && <DataTab s={s} caps={caps} onChange={refresh} />}
        {tab === "results" && <ResultsTab s={s} caps={caps} onChange={refresh} canCalc={can("msa:calculate")} />}
        {tab === "reports" && <ReportsTab s={s} caps={caps} />}
      </div>
    </>
  );
}

function Summary({ s, caps, users, onChange }: { s: MsaStudy; caps: Set<string>; users: Record<string, string>; onChange: () => void }) {
  const { t, fmtDate } = useI18n();
  const { can } = useAuth();
  const [editing, setEditing] = useState(false);
  const [design, setDesign] = useState<Strs>(designState(s.design, s.params));
  const [criteriaId, setCriteriaId] = useState(s.criteria_set_id ?? "");
  const criteria = useResource(() => api.get<CriteriaSet[]>("/msa/criteria", { method: s.method }), [s.method]);
  const [lastError, setLastError] = useState<unknown>(null);
  const [concl, setConcl] = useState<{ decision: Decision; comment: string } | null>(null);
  const { busy, error, run } = useAction();
  useEffect(() => setDesign(designState(s.design, s.params)), [s]);
  const save = () => run("save", async () => {
    setLastError(null);
    try {
      await api.patch(`/msa/studies/${s.id}`, { ...designPayload(s.method, design), criteria_set_id: criteriaId || null });
    } catch (e) { setLastError(e); throw e; }
  }, () => { setEditing(false); onChange(); });
  return (
    <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
      <div className="space-y-4">
        <Card title={t("common.general")}>
          <div className="grid gap-3 sm:grid-cols-3">
            <Spec label={t("msa.characteristic")}>{s.characteristic}</Spec>
            <Spec label={t("msa.partNumber")} mono>{s.part_number ?? "—"} {s.part_revision && `rev ${s.part_revision}`}</Spec>
            <Spec label={t("msa.customer")}>{s.customer ?? "—"}</Spec>
            <Spec label={t("msa.gage")} mono>{s.gage_code} · {s.gage_description}</Spec>
            <Spec label={t("msa.responsible")}>{users[s.responsible_id] ?? "—"}</Spec>
            <Spec label={`${t("msa.start")} / ${t("msa.end")}`}>{fmtDate(s.start_date)} / {fmtDate(s.end_date)}</Spec>
          </div>
          {s.final_comment && <p className="mt-3 text-[13px]"><b>{t("msa.conclusion")}:</b> {s.final_comment}</p>}
        </Card>
        <Card title={t("msa.design")} actions={caps.has("configure") && can("msa:manage") && !editing &&
          <Button onClick={() => setEditing(true)}>{t("common.edit")}</Button>}>
          {error && <Alert>{error}<IssueList error={lastError} /></Alert>}
          <DesignFields method={s.method} value={design} onChange={setDesign} disabled={!editing} />
          <Field label={t("msa.criteria")} className="mt-3">
            <Select disabled={!editing} value={criteriaId} onChange={(e) => setCriteriaId(e.target.value)}>
              <option value="">{t("msa.criteriaAuto")}</option>
              {(criteria.data ?? []).filter((c) => c.status === "APPROVED").map((c) => <option key={c.id} value={c.id}>{c.name} v{c.version}</option>)}
            </Select>
          </Field>
          {editing && <div className="mt-3 flex gap-2"><Button variant="primary" disabled={!!busy} onClick={save}>{t("common.save")}</Button>
            <Button onClick={() => { setEditing(false); setDesign(designState(s.design, s.params)); }}>{t("common.cancel")}</Button></div>}
        </Card>
        <CustomFieldsCard entity="msa_study" id={s.id} canEdit={caps.has("configure") && can("msa:manage")} />
        <DocumentsPanel entityType="msa_study" entityId={s.id} canUpload={can("msa:manage")} />
      </div>
      <div className="space-y-4">
        <WorkflowPanel entity="msa_study" id={s.id} onChange={onChange} users={users} />
        {caps.has("conclude") && can("msa:approve") && (
          <Card title={t("msa.setConclusion")}>
            <p className="mb-2 text-[12px] text-ink-3">{t("msa.conclusionHelp")}</p>
            <Button onClick={() => setConcl({ decision: s.final_decision ?? "ACCEPTABLE", comment: s.final_comment ?? "" })}>{t("msa.setConclusion")}</Button>
          </Card>
        )}
      </div>
      <Modal open={!!concl} title={t("msa.setConclusion")} onClose={() => setConcl(null)}
        footer={<Button variant="primary" disabled={!!busy} onClick={() => concl && run("concl", async () => {
          setLastError(null);
          try { await api.post(`/msa/studies/${s.id}/conclusion`, { decision: concl.decision, comment: concl.comment || null }); }
          catch (e) { setLastError(e); throw e; }
        }, () => { setConcl(null); onChange(); })}>{t("common.save")}</Button>}>
        {error && <Alert>{error}</Alert>}
        {concl && <>
          <Field label={t("msa.decision")}>
            <Select value={concl.decision} onChange={(e) => setConcl({ ...concl, decision: e.target.value as Decision })}>
              {(["ACCEPTABLE", "CONDITIONAL", "NOT_ACCEPTABLE", "INCONCLUSIVE"] as const).map((d) => <option key={d} value={d}>{t(`msa.dec.${d}`)}</option>)}
            </Select>
          </Field>
          <Field label={t("wf.comment")} className="mt-3"><Textarea value={concl.comment} onChange={(e) => setConcl({ ...concl, comment: e.target.value })} /></Field>
        </>}
      </Modal>
    </div>
  );
}

function DataTab({ s, caps, onChange }: { s: MsaStudy; caps: Set<string>; onChange: () => void }) {
  const { t, fmtDateTime } = useI18n();
  const { can } = useAuth();
  const fam = FAMILY[s.method];
  const cols = OBS_FIELDS[fam];
  const [showAll, setShowAll] = useState(false);
  const obs = useResource(() => api.get<MsaObservation[]>(`/msa/studies/${s.id}/observations`, { include_superseded: showAll }), [s.id, showAll]);
  const check = useResource(() => api.get<{ valid: boolean; issues: { code: string; message: string; row?: number }[]; observations: number; planned: number | null }>(`/msa/studies/${s.id}/validation`), [s.id]);
  const seq = useResource(() => api.get<{ step: number; trial: number; operator: string; part: string }[]>(`/msa/studies/${s.id}/sequence`), [s.id]);
  const [paste, setPaste] = useState("");
  const [row, setRow] = useState<Strs>({});
  const [fix, setFix] = useState<{ o: MsaObservation; value: string; reason: string; voiding: boolean } | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState<ImportJob | null>(null);
  const [lastError, setLastError] = useState<unknown>(null);
  const { busy, error, run } = useAction();
  const editable = caps.has("capture") && can("msa:manage");
  const reload = () => { obs.reload(); check.reload(); onChange(); };
  const toRow = (vals: string[]) => Object.fromEntries(cols.map((c, i) => [c, vals[i]?.trim() || undefined]).filter(([, v]) => v !== undefined));
  const post = (rows: Record<string, unknown>[]) => run("rows", async () => {
    setLastError(null);
    try { await api.post(`/msa/studies/${s.id}/observations`, { observations: rows }); } catch (e) { setLastError(e); throw e; }
  }, () => { setPaste(""); setRow({}); reload(); });
  return (
    <div className="space-y-4">
      <Card title={t("msa.validation")}>
        {check.data && (check.data.valid ? <Alert tone="ok">{t("msa.valid")}</Alert> : (
          <Alert tone="warn">
            {check.data.planned !== null && <div>{t("msa.progress", { n: check.data.observations, m: check.data.planned })}</div>}
            <ul className="mt-1 list-disc pl-5 text-[12px]">{check.data.issues.slice(0, 15).map((i, k) => <li key={k}>{i.row ? `${t("issues.row", { n: i.row })}: ` : ""}{i.message}</li>)}</ul>
          </Alert>
        ))}
      </Card>
      {editable && (
        <Card title={t("msa.addRow")}>
          {error && <Alert>{error}<IssueList error={lastError} /></Alert>}
          <div className="grid gap-2 sm:grid-cols-5">
            {cols.map((c) => <Field key={c} label={c}><Input type={c === "measured_at" ? "datetime-local" : "text"} value={row[c] ?? ""}
              onChange={(e) => setRow({ ...row, [c]: e.target.value })} /></Field>)}
            <div className="flex items-end"><Button variant="primary" disabled={!!busy} onClick={() => post([toRow(cols.map((c) => row[c] ?? ""))])}>{t("common.add")}</Button></div>
          </div>
          <details className="mt-3">
            <summary className="cursor-pointer text-[12px] font-semibold">{t("msa.paste")}</summary>
            <p className="my-1 text-[12px] text-ink-3">{t("msa.pasteHelp", { cols: cols.join(" · ") })}</p>
            <Textarea rows={6} className="font-mono text-[12px]" value={paste} onChange={(e) => setPaste(e.target.value)} />
            <Button className="mt-2" disabled={!paste.trim() || !!busy}
              onClick={() => post(paste.split(/\r?\n/).filter((l) => l.trim()).map((l) => toRow(l.split("\t"))))}>{t("msa.saveRows")}</Button>
          </details>
          <details className="mt-3">
            <summary className="cursor-pointer text-[12px] font-semibold">{t("msa.importFile")}</summary>
            <div className="mt-2 flex flex-wrap items-end gap-2">
              <FileInput accept=".csv,.xlsx" onFile={setFile} />
              <Button disabled={!file || !!busy} onClick={() => file && run("imp", async () => {
                setJob(await api.post<ImportJob>("/integrations/imports", form({ importer: "msa_observations", target_id: s.id, file })));
              })}>{t("int.upload")}</Button>
              {job?.status === "VALIDATED" && <Button variant="primary" disabled={!!busy} onClick={() => run("commit", async () => {
                setJob(await api.post<ImportJob>(`/integrations/imports/${job.id}/commit`));
              }, reload)}>{t("int.commit")}</Button>}
            </div>
            {job && <div className="mt-2 text-[12px]"><ToneBadge tone={job.status === "INVALID" ? "bad" : "ok"}>{t(`int.st.${job.status}` as "int.st.VALIDATED")}</ToneBadge>{" "}
              {t("int.rows", { n: job.total_rows, v: job.valid_rows, e: job.error_count })}
              <ul className="mt-1 list-disc pl-5">{job.errors.slice(0, 10).map((e, i) => <li key={i}>{e.row ? `${t("issues.row", { n: e.row })}: ` : ""}{e.errors.join("; ")}</li>)}</ul></div>}
          </details>
        </Card>
      )}
      {!!seq.data?.length && (
        <details className="rounded-md border border-line bg-surface p-3">
          <summary className="cursor-pointer text-[12px] font-semibold">{t("msa.sequence")} ({seq.data.length})</summary>
          <div className="mt-2 max-h-56 overflow-auto font-mono text-[11px]">
            {seq.data.map((st) => <div key={st.step}>{st.step}. T{st.trial} · {st.operator} · {st.part}</div>)}
          </div>
        </details>
      )}
      <Card title={`${t("msa.observations")} (${obs.data?.filter((o) => !o.superseded).length ?? 0})`}
        actions={<Check label={t("msa.showSuperseded")} checked={showAll} onChange={setShowAll} />} flush>
        {!obs.data ? <Loading /> : obs.data.length === 0 ? <EmptyState>{t("msa.noRuns")}</EmptyState> : (
          <div className="max-h-[420px] overflow-auto">
            <table className="data-table">
              <thead><tr>{cols.map((c) => <th key={c}>{c}</th>)}<th>{t("oot.source")}</th><th /></tr></thead>
              <tbody>
                {obs.data.map((o) => (
                  <tr key={o.id} className={o.superseded ? "opacity-50 line-through" : ""}>
                    {cols.map((c) => <td key={c} className="tabular">{c === "measured_at" ? fmtDateTime(o.measured_at)
                      : String((o as unknown as Record<string, unknown>)[c] ?? "—")}</td>)}
                    <td className="text-[11px]">{o.source}{o.correction_reason && <div className="text-ink-3">{o.correction_reason}</div>}</td>
                    <td>{editable && !o.superseded && <div className="flex gap-1">
                      <Button variant="ghost" onClick={() => setFix({ o, value: o.value ?? o.category ?? "", reason: "", voiding: false })}>{t("msa.correct")}</Button>
                      <Button variant="ghost" onClick={() => setFix({ o, value: "", reason: "", voiding: true })}>{t("msa.void")}</Button></div>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <Modal open={!!fix} title={fix?.voiding ? t("msa.void") : t("msa.correct")} onClose={() => setFix(null)}
        footer={<Button variant="primary" disabled={!fix?.reason.trim() || !!busy} onClick={() => fix && run("fix", async () => {
          const replacement = fix.voiding ? null : fam === "ATTRIBUTE" ? { category: fix.value } : { value: fix.value };
          await api.post(`/msa/observations/${fix.o.id}/correct`, { reason: fix.reason, replacement });
        }, () => { setFix(null); reload(); })}>{t("common.save")}</Button>}>
        {error && <Alert>{error}</Alert>}
        {fix && !fix.voiding && <Field label={t("msa.newValue")}><Input value={fix.value} onChange={(e) => setFix({ ...fix, value: e.target.value })} /></Field>}
        {fix && <Field label={t("msa.correctionReason")} required className="mt-3"><Textarea value={fix.reason} onChange={(e) => setFix({ ...fix, reason: e.target.value })} /></Field>}
      </Modal>
    </div>
  );
}

function ResultsTab({ s, caps, onChange, canCalc }: { s: MsaStudy; caps: Set<string>; onChange: () => void; canCalc: boolean }) {
  const { t, fmtDateTime } = useI18n();
  const runs = useResource(() => api.get<RunSummary[]>(`/msa/studies/${s.id}/runs`), [s.id]);
  const [sel, setSel] = useState<string | null>(null);
  const runId = sel ?? runs.data?.[0]?.id ?? null;
  const run = useResource(() => (runId ? api.get<MsaRun>(`/msa/runs/${runId}`) : Promise.resolve(null)), [runId]);
  const [verify, setVerify] = useState<{ identical: boolean; differences: Record<string, unknown> } | null>(null);
  const [lastError, setLastError] = useState<unknown>(null);
  const act = useAction();
  return (
    <div className="space-y-4">
      {act.error && <Alert>{act.error}<IssueList error={lastError} /></Alert>}
      <div className="flex flex-wrap items-center gap-2">
        {caps.has("calculate") && canCalc && <Button variant="primary" disabled={!!act.busy} onClick={() => act.run("calc", async () => {
          setLastError(null);
          try { const r = await api.post<MsaRun>(`/msa/studies/${s.id}/calculate`); setSel(r.id); } catch (e) { setLastError(e); throw e; }
        }, () => { runs.reload(); onChange(); })}>{t("msa.calculate")}</Button>}
        {!!runs.data?.length && (
          <Select value={runId ?? ""} onChange={(e) => { setSel(e.target.value); setVerify(null); }} aria-label={t("msa.runs")} className="w-auto">
            {runs.data.map((r) => <option key={r.id} value={r.id}>{t("msa.run", { n: r.run_number })} · {fmtDateTime(r.calculated_at)} · {t(`msa.dec.${r.decision}`)}</option>)}
          </Select>
        )}
        {run.data && <Button onClick={() => act.run("verify", async () => setVerify(await api.post(`/msa/runs/${run.data!.id}/verify`)))}>{t("msa.verify")}</Button>}
      </div>
      {verify && (verify.identical ? <Alert tone="ok">{t("msa.verifyOk")}</Alert>
        : <Alert tone="warn">{t("msa.verifyDiff", { list: Object.keys(verify.differences).join(", ") })}</Alert>)}
      {!runs.data ? <Loading /> : runs.data.length === 0 ? <EmptyState>{t("msa.noRuns")}</EmptyState>
        : !run.data ? <Loading /> : <RunView run={run.data} />}
    </div>
  );
}

const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v.toFixed(2)} %`);
const n4 = (v: unknown) => (typeof v === "number" ? (Math.abs(v) >= 1000 ? v.toFixed(1) : v.toPrecision(5)) : v === null || v === undefined ? "—" : String(v));

function RunView({ run }: { run: MsaRun }) {
  const { t, fmtDateTime, lang } = useI18n();
  const r: MsaResults = run.results;
  return (
    <div className="space-y-4">
      <Card title={`${t("msa.run", { n: run.run_number })} · ${fmtDateTime(run.calculated_at)}`}
        actions={<ToneBadge tone={DECISION_TONE[run.decision]}>{t(`msa.dec.${run.decision}`)}</ToneBadge>}>
        <div className="grid gap-3 text-[12px] sm:grid-cols-3">
          <Spec label={t("msa.model")}>{r.model}</Spec>
          <Spec label={t("msa.engineLabel")}>{t("msa.engine", { e: run.engine_version, a: run.algorithm_version })} ·{" "}
            {run.validation_status === "VALIDATED" ? t("msa.validated") : t("msa.experimental")}</Spec>
          <Spec label={t("msa.inputHash")} mono>{run.input_hash.slice(0, 20)}…</Spec>
        </div>
      </Card>
      <Card title={t("msa.metrics")}>
        <div className="grid gap-2 sm:grid-cols-4">
          {Object.entries(r.metrics).map(([k, v]) => <Spec key={k} label={k} mono>{typeof v === "boolean" ? (v ? "true" : "false") : n4(v)}</Spec>)}
        </div>
      </Card>
      {r.tables.components && (
        <Card title={t("msa.components")} flush>
          <div className="overflow-x-auto"><table className="data-table">
            <thead><tr><th>Source</th><th>StdDev</th><th>Var</th><th>%Contribution</th><th>%Study Var</th><th>%Tolerance</th></tr></thead>
            <tbody>{(r.tables.components as { source: string; sd: number; variance: number; pct_contribution: number | null; pct_study_var: number | null; pct_tolerance: number | null }[]).map((c) => (
              <tr key={c.source}><td className="font-semibold">{c.source}</td><td className="tabular">{n4(c.sd)}</td><td className="tabular">{n4(c.variance)}</td>
                <td className="tabular">{pct(c.pct_contribution)}</td><td className="tabular">{pct(c.pct_study_var)}</td><td className="tabular">{pct(c.pct_tolerance)}</td></tr>))}</tbody>
          </table></div>
        </Card>
      )}
      {r.tables.anova && (
        <Card title={t("msa.anova")} flush>
          <div className="overflow-x-auto"><table className="data-table">
            <thead><tr><th>Source</th><th>DF</th><th>SS</th><th>MS</th><th>F</th><th>p</th></tr></thead>
            <tbody>{(r.tables.anova as Record<string, number | string | null>[]).map((a) => (
              <tr key={String(a.source)}><td>{a.source}</td><td className="tabular">{a.df}</td><td className="tabular">{n4(a.ss)}</td>
                <td className="tabular">{n4(a.ms)}</td><td className="tabular">{n4(a.f)}</td><td className="tabular">{n4(a.p)}</td></tr>))}</tbody>
          </table></div>
        </Card>
      )}
      <Card title={t("msa.charts")}>
        <MsaCharts run={run} />
      </Card>
      <Card title={t("msa.evaluation")}>
        {!run.evaluation ? <Alert tone="info">{t("msa.noCriteria")}</Alert> : (
          <>
            <table className="data-table"><thead><tr><th>{t("crit.metric")}</th><th>{t("crit.op")}</th><th>{t("crit.value")}</th><th>Actual</th><th>{t("common.status")}</th></tr></thead>
              <tbody>{run.evaluation.map((e, i) => <tr key={i}><td>{e.label ?? e.metric}</td><td>{e.op}</td><td className="tabular">{String(e.value)}</td>
                <td className="tabular">{n4(e.actual)}</td><td><ToneBadge tone={e.status === "PASS" ? "ok" : e.status === "CONDITIONAL" ? "warn" : e.status === "NOT_EVALUATED" ? "mute" : "bad"}>{e.status}</ToneBadge></td></tr>)}</tbody></table>
          </>
        )}
      </Card>
      {!!run.guidance?.length && (
        <Card title={t("msa.guidance")}>
          <ul className="space-y-3">{run.guidance.map((g, i) => (
            <li key={i} className="flex gap-2.5">
              <ToneBadge tone={g.level}>{g.level === "ok" ? "✓" : g.level === "info" ? "i" : "!"}</ToneBadge>
              <div className="text-[13px]">{g[lang]}<div className="mt-0.5 text-[11px] text-ink-3">{g.ref[lang]}</div></div>
            </li>))}</ul>
        </Card>
      )}
      {!!r.warnings.length && <Alert tone="warn"><b>{t("msa.warnings")}</b><ul className="list-disc pl-5">{r.warnings.map((w) => <li key={w}>{w}</li>)}</ul></Alert>}
    </div>
  );
}

function ReportsTab({ s, caps }: { s: MsaStudy; caps: Set<string> }) {
  const { t, fmtDateTime, lang } = useI18n();
  const { can } = useAuth();
  const reports = useResource(() => api.get<MsaReport[]>(`/msa/studies/${s.id}/reports`), [s.id]);
  const runs = useResource(() => api.get<RunSummary[]>(`/msa/studies/${s.id}/runs`), [s.id]);
  const { busy, error, run } = useAction();
  const runNo = (id: string) => runs.data?.find((r) => r.id === id)?.run_number ?? "?";
  return (
    <Card title={t("msa.tab.reports")} actions={caps.has("report") && can("msa:manage") &&
      <Button variant="primary" disabled={!!busy || !runs.data?.length} onClick={() => run("rep", () => api.post(`/msa/studies/${s.id}/reports`, { lang }), reports.reload)}>{t("msa.issueReport")}</Button>}>
      {error && <Alert>{error}</Alert>}
      {!reports.data?.length ? <EmptyState>{t("msa.noReports")}</EmptyState> : (
        <ul className="divide-y divide-line">
          {reports.data.map((r) => (
            <li key={r.id} className="flex items-center justify-between py-2 text-[13px]">
              <span>{t("msa.reportRev", { n: r.revision, r: runNo(r.run_id) })} · {fmtDateTime(r.issued_at)}</span>
              <Button variant="ghost" onClick={() => api.download(`/attachments/${r.attachment_id}/download`, undefined, { open: true })}>{t("common.open")}</Button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
