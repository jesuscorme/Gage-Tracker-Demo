"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { CustomFieldInputs, type Values, useFieldDefs } from "@/components/custom-fields";
import { DesignFields, designPayload, designState, type Strs } from "@/components/msa-design";
import {
  Alert, Button, Card, EmptyState, ErrorState, Field, Input, LinkButton, Loading, Modal, PageHeader, Select, ToneBadge, useAction,
} from "@/components/ui";
import { IssueList } from "@/components/workflow";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { localToday, useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { useGages, usePlants, useUsers } from "@/lib/lookups";
import { DECISION_TONE } from "@/lib/status-b3";
import { MSA_METHODS, type MsaMethod, type MsaStudy } from "@/lib/types-b3";

export default function MsaListPage() {
  const { t, fmtDate } = useI18n();
  const { can } = useAuth();
  const [q, setQ] = useState("");
  const [method, setMethod] = useState("");
  const [creating, setCreating] = useState(false);
  const list = useResource(() => api.get<MsaStudy[]>("/msa/studies", { q, method }), [q, method]);
  return (
    <>
      <PageHeader title={t("msa.title")} actions={<>
        <LinkButton href="/msa/criteria">{t("nav.msaCriteria")}</LinkButton>
        {can("msa:manage") && <Button variant="primary" onClick={() => setCreating(true)}>+ {t("msa.new")}</Button>}
      </>} />
      <Card flush>
        <div className="grid gap-2 border-b border-line p-3 sm:grid-cols-[2fr_1fr]">
          <Input type="search" placeholder={`${t("msa.code")}, ${t("msa.characteristic").toLowerCase()}, ${t("msa.partNumber").toLowerCase()}`}
            value={q} onChange={(e) => setQ(e.target.value)} />
          <Select value={method} onChange={(e) => setMethod(e.target.value)} aria-label={t("msa.method")}>
            <option value="">{t("msa.method")}: {t("common.all")}</option>
            {MSA_METHODS.map((m) => <option key={m} value={m}>{t(`msa.m.${m}`)}</option>)}
          </Select>
        </div>
        {list.error ? <div className="px-4"><ErrorState error={list.error} onRetry={list.reload} /></div>
          : !list.data ? <div className="px-4"><Loading /></div>
          : list.data.length === 0 ? <EmptyState>{t("msa.empty")}</EmptyState>
          : (
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead><tr><th>{t("msa.code")}</th><th>{t("common.title")}</th><th className="hidden md:table-cell">{t("msa.method")}</th>
                  <th className="hidden lg:table-cell">{t("msa.gage")}</th><th>{t("common.status")}</th><th>{t("msa.decision")}</th>
                  <th className="hidden md:table-cell">{t("msa.start")}</th></tr></thead>
                <tbody>
                  {list.data.map((s) => (
                    <tr key={s.id}>
                      <td><Link href={`/msa/${s.id}`} className="font-mono text-[13px] font-semibold text-accent hover:underline">{s.study_code}</Link></td>
                      <td className="max-w-[280px]"><div className="truncate">{s.title}</div>
                        <div className="truncate text-[11px] text-ink-3">{s.characteristic}{s.part_number && ` · ${s.part_number}`}</div></td>
                      <td className="hidden text-[12px] md:table-cell">{t(`msa.m.${s.method}`)}</td>
                      <td className="hidden font-mono text-[12px] lg:table-cell">{s.gage_code}</td>
                      <td><ToneBadge tone="info">{s.status}</ToneBadge></td>
                      <td>{s.final_decision ? <ToneBadge tone={DECISION_TONE[s.final_decision]}>{t(`msa.dec.${s.final_decision}`)}</ToneBadge>
                        : s.latest_decision ? <span className="text-[12px] text-ink-2">{t(`msa.dec.${s.latest_decision}`)}</span> : "—"}</td>
                      <td className="hidden tabular md:table-cell">{fmtDate(s.start_date)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </Card>
      <NewStudy open={creating} onClose={() => setCreating(false)} />
    </>
  );
}

function NewStudy({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const { me } = useAuth();
  const router = useRouter();
  const plants = usePlants();
  const gages = useGages();
  const users = useUsers();
  const defs = useFieldDefs("msa_study");
  const [method, setMethod] = useState<MsaMethod>("GRR_CROSSED_ANOVA");
  const [f, setF] = useState<Strs>({ start_date: localToday() });
  const [design, setDesign] = useState<Strs>(designState());
  const [cf, setCf] = useState<Values>({});
  const [lastError, setLastError] = useState<unknown>(null);
  const { busy, error, run } = useAction();
  const set = (k: string, v: string) => setF({ ...f, [k]: v });
  const submit = () => run("create", async () => {
    setLastError(null);
    try {
      const s = await api.post<MsaStudy>("/msa/studies", {
        title: f.title, method, characteristic: f.characteristic, part_number: f.part_number || null,
        part_revision: f.part_revision || null, customer: f.customer || null,
        plant_id: f.plant_id || plants[0]?.id, gage_id: f.gage_id, responsible_id: f.responsible_id || me?.id,
        start_date: f.start_date, ...designPayload(method, design), custom_fields: cf,
      });
      router.push(`/msa/${s.id}`);
    } catch (e) {
      setLastError(e);
      throw e;
    }
  });
  return (
    <Modal open={open} title={t("msa.new")} onClose={onClose}
      footer={<Button variant="primary" disabled={!!busy || !f.title || !f.characteristic || !f.gage_id} onClick={submit}>{t("common.create")}</Button>}>
      {error && <Alert>{error}<IssueList error={lastError} /></Alert>}
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("msa.method")} required>
          <Select value={method} onChange={(e) => setMethod(e.target.value as MsaMethod)}>
            {MSA_METHODS.map((m) => <option key={m} value={m}>{t(`msa.m.${m}`)}</option>)}
          </Select>
        </Field>
        <Field label={t("common.title")} required><Input value={f.title ?? ""} onChange={(e) => set("title", e.target.value)} /></Field>
        <Field label={t("msa.characteristic")} required><Input value={f.characteristic ?? ""} onChange={(e) => set("characteristic", e.target.value)} /></Field>
        <Field label={t("msa.gage")} required>
          <Select value={f.gage_id ?? ""} onChange={(e) => set("gage_id", e.target.value)}>
            <option value="">—</option>
            {gages.map((g) => <option key={g.id} value={g.id}>{g.gage_code} · {g.description}</option>)}
          </Select>
        </Field>
        <Field label={t("msa.partNumber")}><Input value={f.part_number ?? ""} onChange={(e) => set("part_number", e.target.value)} /></Field>
        <Field label={t("msa.partRevision")}><Input value={f.part_revision ?? ""} onChange={(e) => set("part_revision", e.target.value)} /></Field>
        <Field label={t("msa.customer")}><Input value={f.customer ?? ""} onChange={(e) => set("customer", e.target.value)} /></Field>
        <Field label={t("gage.field.plant")}>
          <Select value={f.plant_id ?? plants[0]?.id ?? ""} onChange={(e) => set("plant_id", e.target.value)}>
            {plants.map((p) => <option key={p.id} value={p.id}>{p.code} · {p.name}</option>)}
          </Select>
        </Field>
        <Field label={t("msa.responsible")}>
          <Select value={f.responsible_id ?? me?.id ?? ""} onChange={(e) => set("responsible_id", e.target.value)}>
            {users.list.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
          </Select>
        </Field>
        <Field label={t("msa.start")} required><Input type="date" value={f.start_date ?? ""} onChange={(e) => set("start_date", e.target.value)} /></Field>
      </div>
      <div className="mt-4 border-t border-line pt-3">
        <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-3">{t("msa.design")}</div>
        <DesignFields method={method} value={design} onChange={setDesign} />
      </div>
      {!!defs.data?.length && <div className="mt-4 border-t border-line pt-3"><CustomFieldInputs defs={defs.data} values={cf} onChange={setCf} /></div>}
    </Modal>
  );
}
