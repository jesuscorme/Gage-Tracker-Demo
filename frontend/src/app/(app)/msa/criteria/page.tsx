"use client";

import { useState } from "react";
import {
  Alert, Button, Card, EmptyState, Field, Input, Loading, Modal, PageHeader, ReasonDialog, Select, Textarea, ToneBadge, useAction,
} from "@/components/ui";
import { IssueList } from "@/components/workflow";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { usePlants, useUsers } from "@/lib/lookups";
import { MSA_METHODS, type CriteriaRule, type CriteriaSet, type CriteriaTemplate, type MethodInfo, type MsaMethod } from "@/lib/types-b3";

export default function CriteriaPage() {
  const { t, fmtDateTime } = useI18n();
  const { can, me } = useAuth();
  const users = useUsers();
  const list = useResource(() => api.get<CriteriaSet[]>("/msa/criteria", { include_retired: true }));
  const [editing, setEditing] = useState(false);
  const [retiring, setRetiring] = useState<CriteriaSet | null>(null);
  const { busy, error, run } = useAction();
  return (
    <>
      <PageHeader title={t("crit.title")} actions={can("msa:criteria") && <Button variant="primary" onClick={() => setEditing(true)}>+ {t("crit.new")}</Button>} />
      {error && <Alert>{error}</Alert>}
      {!list.data ? <Loading /> : list.data.length === 0 ? <Card><EmptyState>{t("crit.empty")}</EmptyState></Card> : (
        <div className="grid gap-3 lg:grid-cols-2">
          {list.data.map((c) => (
            <Card key={c.id} title={`${c.name} · v${c.version}`} actions={<ToneBadge tone={c.status === "APPROVED" ? "ok" : c.status === "DRAFT" ? "warn" : "mute"}>
              {t(`crit.status.${c.status}` as "crit.status.DRAFT")}</ToneBadge>}>
              <div className="text-[12px] text-ink-2">{t(`msa.m.${c.method}`)} · {t(`crit.scope.${c.scope}` as "crit.scope.PLANT")}{c.customer && ` · ${c.customer}`}</div>
              <ul className="mt-2 space-y-0.5 font-mono text-[12px]">
                {c.rules.map((r, i) => <li key={i}>{r.metric} {r.op} {String(r.value)} → {r.outcome ?? "NOT_ACCEPTABLE"}</li>)}
              </ul>
              <p className="mt-2 text-[11px] text-ink-3">{c.source}</p>
              <p className="mt-1 text-[11px] text-ink-3">{users.names[c.created_by]} · {fmtDateTime(c.created_at)}
                {c.approved_at && ` · ✓ ${users.names[c.approved_by ?? ""] ?? ""} ${fmtDateTime(c.approved_at)}`}</p>
              <div className="mt-2 flex gap-2">
                {c.status === "DRAFT" && can("msa:approve") && c.created_by !== me?.id &&
                  <Button variant="primary" disabled={!!busy} onClick={() => run("a", () => api.post(`/msa/criteria/${c.id}/approve`), list.reload)}>{t("crit.approve")}</Button>}
                {c.status !== "RETIRED" && can("msa:criteria") && <Button variant="ghost" onClick={() => setRetiring(c)}>{t("crit.retire")}</Button>}
              </div>
            </Card>
          ))}
        </div>
      )}
      <Editor open={editing} onClose={() => setEditing(false)} onSaved={list.reload} />
      <ReasonDialog open={!!retiring} title={t("crit.retire")} label={t("common.reason")} onClose={() => setRetiring(null)} danger
        onConfirm={(reason) => run("r", () => api.post(`/msa/criteria/${retiring!.id}/retire`, { reason }), () => { setRetiring(null); list.reload(); })} />
    </>
  );
}

function Editor({ open, onClose, onSaved }: { open: boolean; onClose: () => void; onSaved: () => void }) {
  const { t } = useI18n();
  const plants = usePlants();
  const templates = useResource(() => api.get<CriteriaTemplate[]>("/msa/criteria/templates"));
  const methods = useResource(() => api.get<{ methods: MethodInfo[] }>("/msa/methods"));
  const [method, setMethod] = useState<MsaMethod>("GRR_CROSSED_ANOVA");
  const [name, setName] = useState("");
  const [scope, setScope] = useState("ORGANIZATION");
  const [plant, setPlant] = useState("");
  const [customer, setCustomer] = useState("");
  const [source, setSource] = useState("");
  const [rules, setRules] = useState<CriteriaRule[]>([]);
  const [lastError, setLastError] = useState<unknown>(null);
  const { busy, error, run } = useAction();
  const metrics = methods.data?.methods.find((m) => m.code === method)?.metrics ?? [];
  const fromTemplate = (i: number) => {
    const tpl = templates.data![i];
    setName(tpl.name.replace(" (template)", ""));
    setSource(tpl.source);
    setRules(tpl.rules);
    if (!tpl.methods.includes(method)) setMethod(tpl.methods[0]);
  };
  const setRule = (i: number, r: Partial<CriteriaRule>) => setRules(rules.map((x, k) => (k === i ? { ...x, ...r } : x)));
  return (
    <Modal open={open} title={t("crit.new")} onClose={onClose}
      footer={<Button variant="primary" disabled={!!busy || !name || !source || !rules.length} onClick={() => run("save", async () => {
        setLastError(null);
        try {
          await api.post("/msa/criteria", { name, method, scope, plant_id: scope === "PLANT" ? plant || plants[0]?.id : null,
            customer: scope === "CUSTOMER" ? customer : null, source, rules });
        } catch (e) { setLastError(e); throw e; }
      }, () => { onClose(); onSaved(); })}>{t("common.save")}</Button>}>
      {error && <Alert>{error}<IssueList error={lastError} /></Alert>}
      <Field label={t("crit.fromTemplate")}>
        <Select value="" onChange={(e) => e.target.value !== "" && fromTemplate(Number(e.target.value))}>
          <option value="">—</option>
          {(templates.data ?? []).map((tpl, i) => <option key={tpl.name} value={i}>{tpl.name}</option>)}
        </Select>
      </Field>
      <p className="mt-1 text-[11px] text-ink-3">{t("crit.templateNote")}</p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <Field label={t("crit.name")} required><Input value={name} onChange={(e) => setName(e.target.value)} /></Field>
        <Field label={t("msa.method")}><Select value={method} onChange={(e) => setMethod(e.target.value as MsaMethod)}>
          {MSA_METHODS.map((m) => <option key={m} value={m}>{t(`msa.m.${m}`)}</option>)}</Select></Field>
        <Field label={t("crit.scope")}><Select value={scope} onChange={(e) => setScope(e.target.value)}>
          {["ORGANIZATION", "PLANT", "CUSTOMER"].map((s) => <option key={s} value={s}>{t(`crit.scope.${s}` as "crit.scope.PLANT")}</option>)}</Select></Field>
        {scope === "PLANT" && <Field label={t("gage.field.plant")}><Select value={plant} onChange={(e) => setPlant(e.target.value)}>
          {plants.map((p) => <option key={p.id} value={p.id}>{p.code}</option>)}</Select></Field>}
        {scope === "CUSTOMER" && <Field label={t("msa.customer")}><Input value={customer} onChange={(e) => setCustomer(e.target.value)} /></Field>}
      </div>
      <Field label={t("crit.source")} required className="mt-3"><Textarea value={source} onChange={(e) => setSource(e.target.value)} /></Field>
      <div className="mt-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-3">{t("crit.rules")}</div>
      {rules.map((r, i) => (
        <div key={i} className="mt-2 grid grid-cols-[2fr_1fr_1fr_1.5fr_auto] gap-2">
          <Select aria-label={t("crit.metric")} value={r.metric} onChange={(e) => setRule(i, { metric: e.target.value })}>
            {[r.metric, ...metrics.filter((m) => m !== r.metric)].map((m) => <option key={m} value={m}>{m}</option>)}
          </Select>
          <Select aria-label={t("crit.op")} value={r.op} onChange={(e) => setRule(i, { op: e.target.value })}>
            {["lte", "lt", "gte", "gt", "eq"].map((o) => <option key={o} value={o}>{o}</option>)}
          </Select>
          <Input aria-label={t("crit.value")} value={String(r.value)} onChange={(e) => setRule(i, {
            value: e.target.value === "true" ? true : e.target.value === "false" ? false : (Number(e.target.value) as number) })} />
          <Select aria-label={t("crit.outcome")} value={r.outcome ?? "NOT_ACCEPTABLE"} onChange={(e) => setRule(i, { outcome: e.target.value })}>
            <option value="NOT_ACCEPTABLE">{t("msa.dec.NOT_ACCEPTABLE")}</option><option value="CONDITIONAL">{t("msa.dec.CONDITIONAL")}</option>
          </Select>
          <Button variant="ghost" onClick={() => setRules(rules.filter((_, k) => k !== i))}>×</Button>
        </div>
      ))}
      <Button className="mt-2" onClick={() => setRules([...rules, { metric: metrics[0] ?? "", op: "lte", value: 0, outcome: "NOT_ACCEPTABLE" }])}>+ {t("common.add")}</Button>
    </Modal>
  );
}
