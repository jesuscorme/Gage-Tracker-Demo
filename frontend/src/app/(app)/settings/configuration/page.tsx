"use client";

import { useEffect, useState } from "react";
import {
  Alert, Button, Card, Check, EmptyState, Field, Input, Loading, PageHeader, ReasonDialog, Select, Tabs, Textarea, ToneBadge, useAction,
} from "@/components/ui";
import { IssueList } from "@/components/workflow";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { csv, useUsers } from "@/lib/lookups";
import type { ConfigCatalogue, ConfigItem, ConfigVersion } from "@/lib/types-b3";

type Tab = "fields" | "forms" | "workflows" | "matrix" | "rules" | "oot" | "pending";

/** Shared submit helper: propose a new version and surface validation details. */
function usePropose(onDone: () => void) {
  const [lastError, setLastError] = useState<unknown>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const act = useAction();
  const propose = (kind: string, definition: unknown, summary: string) => act.run(kind, async () => {
    setLastError(null);
    try {
      const v = await api.post<ConfigVersion>("/config/items", { kind, definition, change_summary: summary || "Update" });
      setNotice(`v${v.version} · ${v.status}`);
    } catch (e) { setLastError(e); throw e; }
  }, onDone);
  const banner = <>{act.error && <Alert>{act.error}<IssueList error={lastError} /></Alert>}{notice && <Alert tone="ok">{notice}</Alert>}</>;
  return { propose, banner, busy: act.busy };
}

export default function ConfigurationPage() {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("fields");
  const cat = useResource(() => api.get<ConfigCatalogue>("/config/catalogue"));
  const items = useResource(() => api.get<ConfigItem[]>("/config/items"));
  if (!cat.data || !items.data) return <Loading />;
  const props = { cat: cat.data, items: items.data, reload: items.reload };
  return (
    <>
      <PageHeader title={t("cfg.title")} />
      <Tabs value={tab} onChange={setTab} items={[
        { value: "fields", label: t("cfg.tab.fields") }, { value: "forms", label: t("cfg.tab.forms") },
        { value: "workflows", label: t("cfg.tab.workflows") }, { value: "matrix", label: t("cfg.tab.matrix") },
        { value: "rules", label: t("cfg.tab.rules") }, { value: "oot", label: t("oot.settings") },
        { value: "pending", label: `${t("cfg.tab.pending")} (${items.data.filter((i) => i.draft).length})` },
      ]} />
      <div className="mt-4 space-y-4">
        {tab === "fields" && <Fields {...props} />}
        {tab === "forms" && <Forms {...props} />}
        {tab === "workflows" && <Workflows {...props} />}
        {tab === "matrix" && <Matrix {...props} />}
        {tab === "rules" && <Rules {...props} />}
        {tab === "oot" && <OotSettings />}
        {tab === "pending" && <Pending {...props} />}
        <ItemList items={items.data.filter((i) => ({ fields: "CUSTOM_FIELD", forms: "FORM", workflows: "WORKFLOW", matrix: "APPROVAL_MATRIX",
          rules: "BUSINESS_RULE" } as Record<string, string>)[tab] === i.kind)} reload={items.reload} />
      </div>
    </>
  );
}

type P = { cat: ConfigCatalogue; items: ConfigItem[]; reload: () => void };

function ItemList({ items, reload }: { items: ConfigItem[]; reload: () => void }) {
  const { t, fmtDateTime } = useI18n();
  const { can } = useAuth();
  const [open, setOpen] = useState<string | null>(null);
  const [retiring, setRetiring] = useState<ConfigItem | null>(null);
  const versions = useResource(() => (open ? api.get<ConfigVersion[]>(`/config/items/${open}/versions`) : Promise.resolve([])), [open]);
  const { run } = useAction();
  if (!items.length) return null;
  return (
    <Card title={t("cfg.versions")} flush>
      <table className="data-table"><thead><tr><th>{t("cfg.key")}</th><th>{t("common.status")}</th><th /></tr></thead>
        <tbody>{items.map((i) => <tr key={i.id}><td className="font-mono text-[12px]">{i.key}</td>
          <td className="text-[12px]">{i.is_retired ? <ToneBadge tone="mute">{t("cfg.retire")}</ToneBadge> : i.active_version ? t("cfg.active", { n: i.active_version }) : "—"}
            {i.draft && <div><ToneBadge tone="warn">{t("cfg.draft", { n: i.draft.version })}</ToneBadge></div>}</td>
          <td><Button variant="ghost" onClick={() => setOpen(open === i.id ? null : i.id)}>{t("cfg.versions")} ({i.version_count})</Button>
            {!i.is_retired && can("config:manage") && <Button variant="ghost" onClick={() => setRetiring(i)}>{t("cfg.retire")}</Button>}</td></tr>)}</tbody></table>
      {open && versions.data && <div className="space-y-2 border-t border-line p-3">{versions.data.map((v) => (
        <details key={v.id} className="rounded border border-line p-2 text-[12px]">
          <summary className="cursor-pointer">v{v.version} · {v.status} · {v.change_summary} · {fmtDateTime(v.created_at)}{v.decision_comment && ` · “${v.decision_comment}”`}</summary>
          <pre className="mt-2 max-h-64 overflow-auto font-mono text-[11px]">{JSON.stringify(v.definition, null, 2)}</pre>
        </details>))}</div>}
      <ReasonDialog open={!!retiring} title={t("cfg.retire")} label={t("common.reason")} danger onClose={() => setRetiring(null)}
        onConfirm={(reason) => run("r", () => api.post(`/config/items/${retiring!.id}/retire`, { reason }), () => { setRetiring(null); reload(); })} />
    </Card>
  );
}

function Fields({ cat, reload }: P) {
  const { t } = useI18n();
  const [f, setF] = useState<Record<string, string>>({ entity_type: "gage", field_type: "TEXT", text_format: "ANY" });
  const [required, setRequired] = useState(false);
  const { propose, banner, busy } = usePropose(reload);
  const set = (k: string, v: string) => setF({ ...f, [k]: v });
  const submit = () => {
    const d: Record<string, unknown> = { entity_type: f.entity_type, key: f.key, label: f.label, field_type: f.field_type, required };
    if (["LIST", "MULTISELECT"].includes(f.field_type)) d.options = csv(f.options ?? "");
    if (f.field_type === "NUMBER") { if (f.min) d.min_value = Number(f.min); if (f.max) d.max_value = Number(f.max); }
    if (f.field_type === "TEXT") { d.text_format = f.text_format; if (f.max_length) d.max_length = Number(f.max_length); }
    if (f.visible_when?.includes("=")) {
      const [field, value] = f.visible_when.split("=").map((x) => x.trim());
      d.visible_when = { field, equals: value === "true" ? true : value === "false" ? false : value };
    }
    if (f.help_text) d.help_text = f.help_text;
    propose("CUSTOM_FIELD", d, f.summary ?? "");
  };
  return (
    <Card title={t("cfg.tab.fields")}>
      {banner}
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label={t("cfg.entity")}><Select value={f.entity_type} onChange={(e) => set("entity_type", e.target.value)}>
          {Object.keys(cat.field_entities).map((k) => <option key={k} value={k}>{k}</option>)}</Select></Field>
        <Field label={t("cfg.key")} required hint="a-z, 0-9, _"><Input value={f.key ?? ""} onChange={(e) => set("key", e.target.value)} /></Field>
        <Field label={t("cfg.label")} required><Input value={f.label ?? ""} onChange={(e) => set("label", e.target.value)} /></Field>
        <Field label={t("cfg.fieldType")}><Select value={f.field_type} onChange={(e) => set("field_type", e.target.value)}>
          {cat.field_types.map((x) => <option key={x} value={x}>{x}</option>)}</Select></Field>
        {["LIST", "MULTISELECT"].includes(f.field_type) && <Field label={t("cfg.options")}><Input value={f.options ?? ""} onChange={(e) => set("options", e.target.value)} /></Field>}
        {f.field_type === "NUMBER" && <><Field label={t("cfg.min")}><Input value={f.min ?? ""} onChange={(e) => set("min", e.target.value)} /></Field>
          <Field label={t("cfg.max")}><Input value={f.max ?? ""} onChange={(e) => set("max", e.target.value)} /></Field></>}
        {f.field_type === "TEXT" && <Field label={t("cfg.textFormat")}><Select value={f.text_format} onChange={(e) => set("text_format", e.target.value)}>
          {cat.text_formats.map((x) => <option key={x} value={x}>{x}</option>)}</Select></Field>}
        <Field label={t("cfg.visibleWhen")}><Input value={f.visible_when ?? ""} onChange={(e) => set("visible_when", e.target.value)} /></Field>
        <Field label={t("cfg.summary")}><Input value={f.summary ?? ""} onChange={(e) => set("summary", e.target.value)} /></Field>
        <div className="pt-6"><Check label={t("cfg.required")} checked={required} onChange={setRequired} /></div>
      </div>
      <Button className="mt-3" variant="primary" disabled={!f.key || !f.label || !!busy} onClick={submit}>{t("cfg.save")}</Button>
    </Card>
  );
}

function Forms({ cat, reload }: P) {
  const { t } = useI18n();
  const [entity, setEntity] = useState("gage");
  const [text, setText] = useState("");
  const [summary, setSummary] = useState("");
  const { propose, banner, busy } = usePropose(reload);
  return (
    <Card title={t("cfg.tab.forms")}>
      {banner}
      <Field label={t("cfg.entity")}><Select value={entity} onChange={(e) => setEntity(e.target.value)}>
        {Object.keys(cat.field_entities).map((k) => <option key={k} value={k}>{k}</option>)}</Select></Field>
      <p className="mt-2 text-[11px] text-ink-3">{cat.field_entities[entity]?.join(", ")}</p>
      <Field label={t("cfg.sections")} className="mt-2"><Textarea rows={5} className="font-mono text-[12px]" value={text} onChange={(e) => setText(e.target.value)} /></Field>
      <Field label={t("cfg.summary")} className="mt-2"><Input value={summary} onChange={(e) => setSummary(e.target.value)} /></Field>
      <Button className="mt-3" variant="primary" disabled={!text.trim() || !!busy} onClick={() => propose("FORM", {
        entity_type: entity, sections: text.split(/\r?\n/).filter((l) => l.includes(":")).map((l) => {
          const [title, rest] = [l.slice(0, l.indexOf(":")).trim(), l.slice(l.indexOf(":") + 1)];
          return { title, fields: csv(rest) };
        }) }, summary)}>{t("cfg.save")}</Button>
    </Card>
  );
}

function Workflows({ cat, items, reload }: P) {
  const { t } = useI18n();
  const entities = Object.keys(cat.workflow_entities);
  const [entity, setEntity] = useState(entities[0]);
  const active = items.find((i) => i.kind === "WORKFLOW" && i.key === entity && !i.is_retired)?.active?.definition;
  const [text, setText] = useState("");
  const [summary, setSummary] = useState("");
  const [bad, setBad] = useState(false);
  const { propose, banner, busy } = usePropose(reload);
  useEffect(() => setText(JSON.stringify(active ?? cat.workflow_entities[entity].default_definition, null, 2)), [entity, active, cat]);
  const info = cat.workflow_entities[entity];
  return (
    <Card title={t("cfg.tab.workflows")}>
      {banner}
      <Alert tone="info">{t("cfg.needsApproval")}</Alert>
      <Field label={t("cfg.entity")}><Select value={entity} onChange={(e) => setEntity(e.target.value)}>
        {entities.map((k) => <option key={k} value={k}>{k}</option>)}</Select></Field>
      <p className="mt-2 text-[12px] text-ink-3">{active ? "" : t("cfg.default")} · system states: {Object.entries(info.system_states).map(([k, v]) => `${k} (${v})`).join(", ")}
        · capabilities: {info.capabilities.join(", ")}</p>
      <Field label={t("cfg.editJson")} className="mt-2" error={bad ? t("cfg.invalidJson") : undefined}>
        <Textarea rows={18} className="font-mono text-[11px]" value={text} onChange={(e) => { setText(e.target.value); setBad(false); }} />
      </Field>
      <Field label={t("cfg.summary")} className="mt-2"><Input value={summary} onChange={(e) => setSummary(e.target.value)} /></Field>
      <Button className="mt-3" variant="primary" disabled={!!busy} onClick={() => {
        try { propose("WORKFLOW", JSON.parse(text), summary); } catch { setBad(true); }
      }}>{t("cfg.save")}</Button>
    </Card>
  );
}

function Matrix({ cat, reload }: P) {
  const { t } = useI18n();
  const [entity, setEntity] = useState(cat.approval_entities[0]);
  const [rows, setRows] = useState<Record<string, { roles: string; authorization: string }>>({});
  const [summary, setSummary] = useState("");
  const { propose, banner, busy } = usePropose(reload);
  return (
    <Card title={t("cfg.tab.matrix")}>
      {banner}
      <Field label={t("cfg.entity")}><Select value={entity} onChange={(e) => setEntity(e.target.value)}>
        {cat.approval_entities.map((k) => <option key={k} value={k}>{k}</option>)}</Select></Field>
      <p className="mt-1 text-[11px] text-ink-3">{cat.roles.join(", ")}</p>
      <div className="mt-2 space-y-2">{cat.approval_actions.map((a) => (
        <div key={a} className="grid gap-2 sm:grid-cols-[120px_2fr_1fr] sm:items-end">
          <div className="text-[12px] font-semibold">{a}</div>
          <Field label={t("cfg.roles")}><Input value={rows[a]?.roles ?? ""} onChange={(e) => setRows({ ...rows, [a]: { roles: e.target.value, authorization: rows[a]?.authorization ?? "" } })} /></Field>
          <Field label={t("cfg.authorization")}><Select value={rows[a]?.authorization ?? ""} onChange={(e) => setRows({ ...rows, [a]: { roles: rows[a]?.roles ?? "", authorization: e.target.value } })}>
            <option value="">—</option>{cat.activities.map((x) => <option key={x} value={x}>{x}</option>)}</Select></Field>
        </div>))}</div>
      <Field label={t("cfg.summary")} className="mt-2"><Input value={summary} onChange={(e) => setSummary(e.target.value)} /></Field>
      <Button className="mt-3" variant="primary" disabled={!!busy} onClick={() => propose("APPROVAL_MATRIX", {
        entity_type: entity, actions: Object.fromEntries(Object.entries(rows).filter(([, v]) => v.roles.trim() || v.authorization)
          .map(([k, v]) => [k, { roles: csv(v.roles), authorization: v.authorization || null }])) }, summary)}>{t("cfg.save")}</Button>
    </Card>
  );
}

function Rules({ cat, reload }: P) {
  const { t } = useI18n();
  const entities = Object.keys(cat.workflow_entities);
  const [f, setF] = useState<Record<string, string>>({ entity_type: entities[0], transitions: "*", match: "all", effect: "BLOCK" });
  const { propose, banner, busy } = usePropose(reload);
  const set = (k: string, v: string) => setF({ ...f, [k]: v });
  const parse = (v: string) => (v === "true" ? true : v === "false" ? false : v !== "" && !Number.isNaN(Number(v)) ? Number(v) : v.startsWith("[") ? JSON.parse(v) : v);
  return (
    <Card title={t("cfg.tab.rules")}>
      {banner}
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label={t("cfg.entity")}><Select value={f.entity_type} onChange={(e) => set("entity_type", e.target.value)}>
          {entities.map((k) => <option key={k} value={k}>{k}</option>)}</Select></Field>
        <Field label={t("cfg.ruleName")} required><Input value={f.name ?? ""} onChange={(e) => set("name", e.target.value)} /></Field>
        <Field label={t("cfg.transitions")}><Input value={f.transitions} onChange={(e) => set("transitions", e.target.value)} /></Field>
        <Field label="Match"><Select value={f.match} onChange={(e) => set("match", e.target.value)}><option value="all">all</option><option value="any">any</option></Select></Field>
        <Field label={t("cfg.effect")}><Select value={f.effect} onChange={(e) => set("effect", e.target.value)}><option value="BLOCK">BLOCK</option><option value="WARN">WARN</option></Select></Field>
        <Field label={t("cfg.message")} required><Input value={f.message ?? ""} onChange={(e) => set("message", e.target.value)} /></Field>
      </div>
      <Field label={t("cfg.conditions")} className="mt-2" hint={cat.operators.join(" · ")}>
        <Textarea rows={4} className="font-mono text-[12px]" value={f.conditions ?? ""} onChange={(e) => set("conditions", e.target.value)} />
      </Field>
      <p className="mt-1 text-[11px] text-ink-3">{t("cfg.facts")}: {Object.entries(cat.workflow_entities[f.entity_type].facts).map(([k, v]) => `${k} (${v})`).join(", ")}</p>
      <Button className="mt-3" variant="primary" disabled={!f.name || !f.message || !f.conditions || !!busy} onClick={() => propose("BUSINESS_RULE", {
        entity_type: f.entity_type, name: f.name, transitions: csv(f.transitions), match: f.match, effect: f.effect, message: f.message,
        conditions: (f.conditions ?? "").split(/\r?\n/).filter((l) => l.trim()).map((l) => {
          const [fact, op, ...rest] = l.trim().split(/\s+/);
          return { fact, op, value: rest.length ? parse(rest.join(" ")) : null };
        }) }, f.name ?? "")}>{t("cfg.save")}</Button>
    </Card>
  );
}

function OotSettings() {
  const { t } = useI18n();
  const { can } = useAuth();
  const s = useResource(() => api.get<{ restrict_on_detection: boolean; auto_create_from_calibration: boolean; close_requirements: string[];
    version: number; available_requirements: string[] }>("/oot/settings"));
  const [draft, setDraft] = useState<{ restrict_on_detection: boolean; auto_create_from_calibration: boolean; close_requirements: string[] } | null>(null);
  const { busy, error, run } = useAction();
  useEffect(() => { if (s.data) setDraft(s.data); }, [s.data]);
  if (!draft || !s.data) return <Loading />;
  const edit = can("oot:approve");
  return (
    <Card title={`${t("oot.settings")} · v${s.data.version}`}>
      {error && <Alert>{error}</Alert>}
      <div className="space-y-2">
        <Check label={t("oot.restrictOnDetection")} checked={draft.restrict_on_detection} disabled={!edit} onChange={(c) => setDraft({ ...draft, restrict_on_detection: c })} />
        <Check label={t("oot.autoCreate")} checked={draft.auto_create_from_calibration} disabled={!edit} onChange={(c) => setDraft({ ...draft, auto_create_from_calibration: c })} />
        <div className="pt-2 text-[11px] font-semibold uppercase text-ink-3">{t("oot.closeRequirements")}</div>
        {s.data.available_requirements.map((r) => <Check key={r} label={t(`oot.req.${r}` as "oot.req.disposition")} disabled={!edit}
          checked={draft.close_requirements.includes(r)} onChange={(c) => setDraft({ ...draft, close_requirements: c
            ? [...draft.close_requirements, r] : draft.close_requirements.filter((x) => x !== r) })} />)}
      </div>
      {edit && <Button className="mt-3" variant="primary" disabled={!!busy} onClick={() => run("s", () => api.put("/oot/settings", draft), s.reload)}>{t("common.save")}</Button>}
    </Card>
  );
}

function Pending({ items, reload }: P) {
  const { t, fmtDateTime } = useI18n();
  const { can, me } = useAuth();
  const users = useUsers();
  const [rejecting, setRejecting] = useState<ConfigVersion | null>(null);
  const { busy, error, run } = useAction();
  const drafts = items.filter((i) => i.draft);
  if (!drafts.length) return <Card><EmptyState>{t("cfg.noPending")}</EmptyState></Card>;
  return (
    <div className="space-y-3">
      {error && <Alert>{error}</Alert>}
      {drafts.map((i) => (
        <Card key={i.id} title={`${i.kind} · ${i.key} · v${i.draft!.version}`}>
          <p className="text-[12px] text-ink-2">{i.draft!.change_summary} · {users.names[i.draft!.created_by] ?? ""} · {fmtDateTime(i.draft!.created_at)}</p>
          <pre className="mt-2 max-h-56 overflow-auto rounded bg-surface-2 p-2 font-mono text-[11px]">{JSON.stringify(i.draft!.definition, null, 2)}</pre>
          {can("config:approve") && i.draft!.created_by !== me?.id && <div className="mt-2 flex gap-2">
            <Button variant="primary" disabled={!!busy} onClick={() => run("a", () => api.post(`/config/versions/${i.draft!.id}/approve`, {}), reload)}>{t("cfg.approve")}</Button>
            <Button variant="danger" onClick={() => setRejecting(i.draft!)}>{t("cfg.reject")}</Button></div>}
        </Card>
      ))}
      <ReasonDialog open={!!rejecting} title={t("cfg.reject")} label={t("common.reason")} danger onClose={() => setRejecting(null)}
        onConfirm={(comment) => run("r", () => api.post(`/config/versions/${rejecting!.id}/reject`, { comment }), () => { setRejecting(null); reload(); })} />
    </div>
  );
}
