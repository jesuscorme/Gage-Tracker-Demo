"use client";

import { useEffect, useState } from "react";
import {
  Alert, Button, Card, Check, EmptyState, ErrorState, Field, Input, Loading, Modal, PageHeader, ReasonDialog, Select,
  Tabs, ToneBadge, errorText,
} from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { localToday, useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import type { MessageKey } from "@/lib/messages";
import { AUTH_ACTIVITIES, AUTH_STATE_TONE, MATRIX_TONE, PROFILE_TYPES } from "@/lib/status";
import type { AuthorizationT, Competency, CompetencyRecord, GageType, Matrix, Person, Plant } from "@/lib/types";

type Tab = "people" | "matrix" | "authorizations" | "catalog";

export default function CompetencyPage() {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("people");
  return (
    <>
      <PageHeader title={t("comp.title")} />
      <Tabs<Tab> value={tab} onChange={setTab} items={[
        { value: "people", label: t("comp.tab.people") },
        { value: "matrix", label: t("comp.tab.matrix") },
        { value: "authorizations", label: t("comp.tab.authorizations") },
        { value: "catalog", label: t("comp.tab.catalog") },
      ]} />
      {tab === "people" && <People />}
      {tab === "matrix" && <MatrixView />}
      {tab === "authorizations" && <Authorizations />}
      {tab === "catalog" && <Catalog />}
    </>
  );
}

function People() {
  const { t } = useI18n();
  const { can } = useAuth();
  const people = useResource(() => api.get<Person[]>("/competency/people"));
  const [editing, setEditing] = useState<Person | null>(null);
  const [recordFor, setRecordFor] = useState<Person | null>(null);
  if (people.error) return <ErrorState error={people.error} onRetry={people.reload} />;
  if (!people.data) return <Loading />;
  return (
    <Card flush>
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead><tr><th>{t("common.name")}</th><th>{t("comp.jobTitle")}</th><th>{t("comp.profileTypes")}</th><th>{t("comp.tab.authorizations")}</th><th /></tr></thead>
          <tbody>
            {people.data.map((p) => (
              <tr key={p.user_id}>
                <td><div className="font-medium">{p.full_name}</div><div className="text-[11px] text-ink-3">{p.employee_number ? `#${p.employee_number} · ` : ""}{p.email}</div></td>
                <td className="text-[12px]">{p.has_profile ? p.job_title ?? "—" : <span className="text-ink-3">{t("comp.noProfile")}</span>}</td>
                <td><div className="flex flex-wrap gap-1">{p.profile_types.map((x) => <ToneBadge key={x} tone="info">{t(`comp.ptype.${x}` as MessageKey)}</ToneBadge>)}</div></td>
                <td><div className="flex flex-wrap gap-1">{p.current_authorizations.map((x) => <ToneBadge key={x} tone="ok">{t(`comp.act.${x}` as MessageKey)}</ToneBadge>)}</div></td>
                <td className="whitespace-nowrap text-right">
                  {can("competency:manage") && (
                    <>
                      <Button variant="ghost" className="h-7 px-2" onClick={() => setEditing(p)}>{t("comp.profile")}</Button>
                      <Button variant="ghost" className="h-7 px-2" onClick={() => setRecordFor(p)}>+ {t("comp.record.TRAINING")}</Button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editing && <ProfileDialog person={editing} onClose={() => setEditing(null)} onDone={() => { setEditing(null); people.reload(); }} />}
      {recordFor && <RecordDialog person={recordFor} onClose={() => setRecordFor(null)} onDone={() => { setRecordFor(null); people.reload(); }} />}
    </Card>
  );
}

function ProfileDialog({ person, onClose, onDone }: { person: Person; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const plants = useResource(() => api.get<Plant[]>("/plants"));
  const [f, setF] = useState({ employee_number: person.employee_number ?? "", job_title: person.job_title ?? "",
    plant_id: person.plant_id ?? "", profile_types: person.profile_types, notes: person.notes ?? "" });
  const [error, setError] = useState<string | null>(null);
  const save = () => api.put(`/competency/people/${person.user_id}`, {
    employee_number: f.employee_number || null, job_title: f.job_title || null, plant_id: f.plant_id || null,
    profile_types: f.profile_types, notes: f.notes || null, is_active: true,
  }).then(onDone, (e) => setError(errorText(t, e)));
  return (
    <Modal open title={`${t("comp.profile")} · ${person.full_name}`} onClose={onClose}
      footer={<><Button onClick={onClose}>{t("common.cancel")}</Button><Button variant="primary" onClick={save}>{t("common.save")}</Button></>}>
      {error && <Alert>{error}</Alert>}
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("comp.employee")}><Input value={f.employee_number} onChange={(e) => setF({ ...f, employee_number: e.target.value })} /></Field>
        <Field label={t("comp.jobTitle")}><Input value={f.job_title} onChange={(e) => setF({ ...f, job_title: e.target.value })} /></Field>
        <Field label={t("gage.field.plant")}>
          <Select value={f.plant_id} onChange={(e) => setF({ ...f, plant_id: e.target.value })}>
            <option value="">—</option>{plants.data?.map((p) => <option key={p.id} value={p.id}>{p.code} — {p.name}</option>)}
          </Select>
        </Field>
      </div>
      <fieldset>
        <legend className="mb-1 text-[12px] font-medium text-ink-2">{t("comp.profileTypes")}</legend>
        <div className="grid gap-1.5 sm:grid-cols-2">
          {PROFILE_TYPES.map((pt) => (
            <Check key={pt} label={t(`comp.ptype.${pt}`)} checked={f.profile_types.includes(pt)}
              onChange={(v) => setF({ ...f, profile_types: v ? [...f.profile_types, pt] : f.profile_types.filter((x) => x !== pt) })} />
          ))}
        </div>
      </fieldset>
    </Modal>
  );
}

function RecordDialog({ person, onClose, onDone }: { person: Person; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const comps = useResource(() => api.get<Competency[]>("/competency/competencies"));
  const [f, setF] = useState({ competency_id: "", record_type: "TRAINING", title: "", provider: "", completed_on: "", valid_until: "", result: "PASSED", score: "" });
  const [error, setError] = useState<string | null>(null);
  const s = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  const save = () => api.post("/competency/records", {
    user_id: person.user_id, ...f, provider: f.provider || null, valid_until: f.valid_until || null, score: f.score || null,
  }).then(onDone, (e) => setError(errorText(t, e)));
  return (
    <Modal open title={`${t("comp.record.add")} · ${person.full_name}`} onClose={onClose}
      footer={<><Button onClick={onClose}>{t("common.cancel")}</Button>
        <Button variant="primary" disabled={!f.competency_id || !f.title || !f.completed_on} onClick={save}>{t("common.save")}</Button></>}>
      {error && <Alert>{error}</Alert>}
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("comp.competency")} required className="sm:col-span-2">
          <Select value={f.competency_id} onChange={s("competency_id")}>
            <option value="" />{comps.data?.filter((c) => c.is_active).map((c) => <option key={c.id} value={c.id}>{c.code} — {c.name}</option>)}
          </Select>
        </Field>
        <Field label={t("comp.record.type")}>
          <Select value={f.record_type} onChange={s("record_type")}>
            {(["TRAINING", "EVALUATION", "CERTIFICATION"] as const).map((r) => <option key={r} value={r}>{t(`comp.record.${r}`)}</option>)}
          </Select>
        </Field>
        <Field label={t("common.result")}>
          <Select value={f.result} onChange={s("result")}>
            {(["PASSED", "FAILED", "NOT_APPLICABLE"] as const).map((r) => <option key={r} value={r}>{t(`comp.result.${r}`)}</option>)}
          </Select>
        </Field>
        <Field label={t("common.title")} required className="sm:col-span-2"><Input value={f.title} onChange={s("title")} /></Field>
        <Field label={t("comp.record.provider")}><Input value={f.provider} onChange={s("provider")} /></Field>
        <Field label={t("comp.record.completed")} required><Input type="date" className="font-mono" value={f.completed_on} onChange={s("completed_on")} /></Field>
        <Field label={t("std.validUntil")}><Input type="date" className="font-mono" value={f.valid_until} onChange={s("valid_until")} /></Field>
        <Field label="Score"><Input value={f.score} onChange={s("score")} /></Field>
      </div>
    </Modal>
  );
}

function MatrixView() {
  const { t } = useI18n();
  const m = useResource(() => api.get<Matrix>("/competency/matrix"));
  if (m.error) return <ErrorState error={m.error} onRetry={m.reload} />;
  if (!m.data) return <Loading />;
  if (!m.data.competencies.length || !m.data.rows.length) return <Card><EmptyState>{t("comp.empty")}</EmptyState></Card>;
  return (
    <Card flush>
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr><th>{t("common.name")}</th>{m.data.competencies.map((c) => <th key={c.id} title={c.name} className="text-center font-mono">{c.code}</th>)}</tr>
          </thead>
          <tbody>
            {m.data.rows.map((r) => (
              <tr key={r.user_id}>
                <td><div className="font-medium">{r.full_name}</div><div className="text-[11px] text-ink-3">{r.job_title}</div></td>
                {m.data!.competencies.map((c) => (
                  <td key={c.id} className="text-center">
                    {r.cells[c.id] === "NONE" ? <span className="text-ink-3">—</span>
                      : <ToneBadge tone={MATRIX_TONE[r.cells[c.id]]}>{t(`comp.cell.${r.cells[c.id]}`)}</ToneBadge>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Authorizations() {
  const { t, fmtDate } = useI18n();
  const { can } = useAuth();
  const [revoked, setRevoked] = useState(false);
  const list = useResource(() => api.get<AuthorizationT[]>("/competency/authorizations", { include_revoked: revoked }), [revoked]);
  const types = useResource(() => api.get<GageType[]>("/gage-types", { include_inactive: true }));
  const plants = useResource(() => api.get<Plant[]>("/plants"));
  const [granting, setGranting] = useState(false);
  const [revoking, setRevoking] = useState<AuthorizationT | null>(null);
  const typeName = (id: string | null) => (id ? types.data?.find((x) => x.id === id)?.code ?? "…" : t("comp.auth.allTypes"));
  const plantName = (id: string | null) => (id ? plants.data?.find((x) => x.id === id)?.code ?? "…" : t("comp.auth.allPlants"));
  return (
    <Card flush title={t("comp.tab.authorizations")} actions={
      <div className="flex items-center gap-3">
        <Check label={t("comp.auth.state.REVOKED")} checked={revoked} onChange={setRevoked} />
        {can("competency:authorize") && <Button variant="primary" className="h-8" onClick={() => setGranting(true)}>+ {t("comp.auth.grant")}</Button>}
      </div>}>
      {!list.data ? <div className="px-4"><Loading /></div> : list.data.length === 0 ? <EmptyState>{t("comp.empty")}</EmptyState> : (
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead><tr><th>{t("common.user")}</th><th>{t("comp.auth.activity")}</th><th>{t("comp.auth.scope")}</th><th>{t("common.from")}</th>
              <th>{t("common.to")}</th><th>{t("comp.auth.basis")}</th><th>{t("common.status")}</th><th /></tr></thead>
            <tbody>
              {list.data.map((a) => (
                <tr key={a.id}>
                  <td className="font-medium">{a.user_name}</td>
                  <td>{t(`comp.act.${a.activity}` as MessageKey)}</td>
                  <td className="font-mono text-[12px]">{typeName(a.gage_type_id)} · {plantName(a.plant_id)}</td>
                  <td className="tabular">{fmtDate(a.valid_from)}</td>
                  <td className="tabular">{fmtDate(a.valid_until)}</td>
                  <td className="max-w-[200px] truncate text-[12px]">{a.revoke_reason ? `↯ ${a.revoke_reason}` : a.basis ?? "—"}</td>
                  <td><ToneBadge tone={AUTH_STATE_TONE[a.state]}>{t(`comp.auth.state.${a.state}`)}</ToneBadge></td>
                  <td>{can("competency:authorize") && !a.revoked_at && <Button variant="ghost" className="h-7 px-2 text-bad" onClick={() => setRevoking(a)}>{t("comp.auth.revoke")}</Button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {granting && <GrantDialog types={types.data ?? []} plants={plants.data ?? []} onClose={() => setGranting(false)} onDone={() => { setGranting(false); list.reload(); }} />}
      <ReasonDialog open={!!revoking} title={`${t("comp.auth.revoke")} · ${revoking?.user_name ?? ""}`} label={t("common.reasonRequired")} danger
        onClose={() => setRevoking(null)} onConfirm={(reason) => api.post(`/competency/authorizations/${revoking!.id}/revoke`, { reason }).then(list.reload)} />
    </Card>
  );
}

function GrantDialog({ types, plants, onClose, onDone }: { types: GageType[]; plants: Plant[]; onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const people = useResource(() => api.get<Person[]>("/competency/people"));
  const [f, setF] = useState({ user_id: "", activity: "INTERNAL_CALIBRATION", gage_type_id: "", plant_id: "", valid_from: "", valid_until: "", basis: "", competency_record_id: "" });
  const records = useResource(() => (f.user_id ? api.get<CompetencyRecord[]>("/competency/records", { user_id: f.user_id }) : Promise.resolve([])), [f.user_id]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setF((x) => ({ ...x, valid_from: localToday() })), []);
  const s = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  const save = () => api.post("/competency/authorizations", {
    ...f, gage_type_id: f.gage_type_id || null, plant_id: f.plant_id || null, valid_until: f.valid_until || null,
    basis: f.basis || null, competency_record_id: f.competency_record_id || null,
  }).then(onDone, (e) => setError(errorText(t, e)));
  return (
    <Modal open title={t("comp.auth.grant")} onClose={onClose}
      footer={<><Button onClick={onClose}>{t("common.cancel")}</Button><Button variant="primary" disabled={!f.user_id || !f.valid_from} onClick={save}>{t("common.save")}</Button></>}>
      {error && <Alert>{error}</Alert>}
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("common.user")} required>
          <Select value={f.user_id} onChange={s("user_id")}><option value="" />{people.data?.map((p) => <option key={p.user_id} value={p.user_id}>{p.full_name}</option>)}</Select>
        </Field>
        <Field label={t("comp.auth.activity")} required>
          <Select value={f.activity} onChange={s("activity")}>{AUTH_ACTIVITIES.map((a) => <option key={a} value={a}>{t(`comp.act.${a}`)}</option>)}</Select>
        </Field>
        <Field label={t("gage.field.type")}>
          <Select value={f.gage_type_id} onChange={s("gage_type_id")}><option value="">{t("comp.auth.allTypes")}</option>{types.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</Select>
        </Field>
        <Field label={t("gage.field.plant")}>
          <Select value={f.plant_id} onChange={s("plant_id")}><option value="">{t("comp.auth.allPlants")}</option>{plants.map((x) => <option key={x.id} value={x.id}>{x.code}</option>)}</Select>
        </Field>
        <Field label={t("common.from")} required><Input type="date" className="font-mono" value={f.valid_from} onChange={s("valid_from")} /></Field>
        <Field label={t("common.to")}><Input type="date" className="font-mono" value={f.valid_until} onChange={s("valid_until")} /></Field>
        <Field label={t("comp.competency")} className="sm:col-span-2">
          <Select value={f.competency_record_id} onChange={s("competency_record_id")}>
            <option value="">—</option>{records.data?.filter((r) => r.result === "PASSED").map((r) => <option key={r.id} value={r.id}>{r.title} · {r.completed_on}</option>)}
          </Select>
        </Field>
        <Field label={t("comp.auth.basis")} className="sm:col-span-2"><Input value={f.basis} onChange={s("basis")} /></Field>
      </div>
    </Modal>
  );
}

function Catalog() {
  const { t } = useI18n();
  const { can } = useAuth();
  const list = useResource(() => api.get<Competency[]>("/competency/competencies"));
  const [f, setF] = useState({ code: "", name: "", validity_months: "" });
  const [error, setError] = useState<string | null>(null);
  const add = () => api.post("/competency/competencies", { code: f.code, name: f.name, validity_months: f.validity_months ? Number(f.validity_months) : null })
    .then(() => { setF({ code: "", name: "", validity_months: "" }); list.reload(); }, (e) => setError(errorText(t, e)));
  return (
    <Card flush>
      {list.data?.length ? (
        <table className="data-table">
          <thead><tr><th>{t("common.code")}</th><th>{t("common.name")}</th><th>{t("comp.validityMonths")}</th><th>{t("common.status")}</th></tr></thead>
          <tbody>{list.data.map((c) => (
            <tr key={c.id}><td className="font-mono font-semibold">{c.code}</td><td>{c.name}</td><td className="tabular">{c.validity_months ?? "—"}</td>
              <td>{c.is_active ? t("common.active") : t("common.inactive")}</td></tr>
          ))}</tbody>
        </table>
      ) : <EmptyState>{t("comp.empty")}</EmptyState>}
      {can("competency:manage") && (
        <div className="grid gap-2 border-t border-line bg-line-2/40 px-4 py-3 sm:grid-cols-[140px_1fr_140px_auto]">
          {error && <div className="sm:col-span-4"><Alert>{error}</Alert></div>}
          <Input placeholder={t("common.code")} className="font-mono uppercase" value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} />
          <Input placeholder={t("common.name")} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
          <Input placeholder={t("comp.validityMonths")} type="number" min={1} value={f.validity_months} onChange={(e) => setF({ ...f, validity_months: e.target.value })} />
          <Button variant="primary" disabled={!f.code || f.name.length < 2} onClick={add}>+ {t("common.add")}</Button>
        </div>
      )}
    </Card>
  );
}
