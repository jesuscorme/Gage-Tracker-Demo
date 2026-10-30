"use client";

import { useEffect, useState } from "react";
import {
  Alert, Button, Card, Check, EmptyState, Field, FileInput, Input, Loading, Modal, PageHeader, ReasonDialog, Select, Tabs,
  ToneBadge, useAction,
} from "@/components/ui";
import { IssueList } from "@/components/workflow";
import { api, form } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { useGages, usePlants } from "@/lib/lookups";
import { DELIVERY_TONE, IMPORT_TONE } from "@/lib/status-b3";
import type {
  AdapterInfo, ApiClientRow, Delivery, Device, ImportJob, Importer, MsaStudy, Reading, Webhook,
} from "@/lib/types-b3";

type Tab = "imports" | "api" | "webhooks" | "devices" | "events";

export default function IntegrationsPage() {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("imports");
  return (
    <>
      <PageHeader title={t("int.title")} />
      <Tabs value={tab} onChange={setTab} items={(["imports", "api", "webhooks", "devices", "events"] as const).map((v) => ({ value: v, label: t(`int.tab.${v}`) }))} />
      <div className="mt-4">
        {tab === "imports" && <Imports />}
        {tab === "api" && <ApiClients />}
        {tab === "webhooks" && <Webhooks />}
        {tab === "devices" && <Devices />}
        {tab === "events" && <Events />}
      </div>
    </>
  );
}

function Imports() {
  const { t, fmtDateTime } = useI18n();
  const importers = useResource(() => api.get<Importer[]>("/integrations/importers"));
  const studies = useResource(() => api.get<MsaStudy[]>("/msa/studies", { status: "DRAFT" }));
  const history = useResource(() => api.get<ImportJob[]>("/integrations/imports"));
  const [code, setCode] = useState("gages");
  const [target, setTarget] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState<ImportJob | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [headers, setHeaders] = useState<string[]>([]);
  const { busy, error, run } = useAction();
  const imp = importers.data?.find((i) => i.code === code);
  useEffect(() => { if (job) setMapping(job.mapping); }, [job]);
  const readHeaders = async (f: File | null) => {
    setFile(f);
    if (f && f.name.toLowerCase().endsWith(".csv")) {
      const first = (await f.text()).split(/\r?\n/)[0] ?? "";
      const sep = first.includes(";") ? ";" : first.includes("\t") ? "\t" : ",";
      setHeaders(first.split(sep).map((h) => h.trim()).filter(Boolean));
    } else setHeaders([]);
  };
  const cols = headers.length ? headers : Array.from(new Set(Object.values(mapping)));
  return (
    <div className="space-y-4">
      <Card title={t("int.tab.imports")}>
        {error && <Alert>{error}</Alert>}
        <div className="grid gap-3 sm:grid-cols-[1fr_1fr_2fr_auto] sm:items-end">
          <Field label={t("int.importer")}><Select value={code} onChange={(e) => { setCode(e.target.value); setJob(null); }}>
            {(importers.data ?? []).filter((i) => i.allowed).map((i) => <option key={i.code} value={i.code}>{i.label}</option>)}</Select></Field>
          {imp?.target ? <Field label={imp.target}><Select value={target} onChange={(e) => setTarget(e.target.value)}>
            <option value="">—</option>{(studies.data ?? []).map((s) => <option key={s.id} value={s.id}>{s.study_code} · {s.title}</option>)}</Select></Field> : <div />}
          <FileInput accept=".csv,.xlsx" onFile={readHeaders} />
          <div className="flex gap-2">
            <Button variant="primary" disabled={!file || !!busy} onClick={() => run("up", async () => {
              setJob(await api.post<ImportJob>("/integrations/imports", form({ importer: code, target_id: target || null, file })));
            }, history.reload)}>{t("int.upload")}</Button>
            <Button variant="ghost" onClick={() => api.download(`/integrations/importers/${code}/template`)}>{t("int.template")}</Button>
          </div>
        </div>
      </Card>
      {job && imp && (
        <Card title={`${job.filename}`} actions={<ToneBadge tone={IMPORT_TONE[job.status]}>{t(`int.st.${job.status}` as "int.st.VALIDATED")}</ToneBadge>}>
          <p className="text-[13px]">{t("int.rows", { n: job.total_rows, v: job.valid_rows, e: job.error_count })}</p>
          {job.errors.length > 0 && <Alert><ul className="list-disc pl-5 text-[12px]">{job.errors.slice(0, 25).map((e, i) =>
            <li key={i}>{e.row ? `${t("issues.row", { n: e.row })}${e.key ? ` (${e.key})` : ""}: ` : ""}{e.errors.join("; ")}</li>)}</ul></Alert>}
          <div className="mt-3 text-[11px] font-semibold uppercase text-ink-3">{t("int.mapping")}</div>
          <div className="mt-1 grid gap-2 sm:grid-cols-3">
            {imp.fields.map((f) => (
              <Field key={f.name} label={f.name} required={f.required}>
                <Select value={mapping[f.name] ?? ""} onChange={(e) => {
                  const m = { ...mapping };
                  if (e.target.value) m[f.name] = e.target.value; else delete m[f.name];
                  setMapping(m);
                }}>
                  <option value="">{t("int.notMapped")}</option>
                  {cols.map((c) => <option key={c} value={c}>{c}</option>)}
                </Select>
              </Field>
            ))}
          </div>
          <div className="mt-3 flex gap-2">
            {job.status !== "COMMITTED" && <Button disabled={!!busy} onClick={() => run("re", async () => {
              setJob(await api.post<ImportJob>(`/integrations/imports/${job.id}/reprocess`, { mapping }));
            }, history.reload)}>{t("int.reprocess")}</Button>}
            {job.status === "VALIDATED" && <Button variant="primary" disabled={!!busy} onClick={() => run("ci", async () => {
              setJob(await api.post<ImportJob>(`/integrations/imports/${job.id}/commit`));
            }, history.reload)}>{t("int.commit")}</Button>}
          </div>
          {job.preview.length > 0 && <>
            <div className="mt-3 text-[11px] font-semibold uppercase text-ink-3">{t("int.preview")}</div>
            <div className="max-h-64 overflow-auto"><table className="data-table"><thead><tr>{Object.keys(job.preview[0]).map((k) => <th key={k}>{k}</th>)}</tr></thead>
              <tbody>{job.preview.map((r, i) => <tr key={i}>{Object.values(r).map((v, k) => <td key={k} className="text-[12px]">{v ?? ""}</td>)}</tr>)}</tbody></table></div>
          </>}
        </Card>
      )}
      <Card title={t("int.history")} flush>
        {!history.data?.length ? <EmptyState>—</EmptyState> : (
          <table className="data-table"><thead><tr><th>{t("common.date")}</th><th>{t("int.importer")}</th><th>File</th><th>{t("common.status")}</th><th>Rows</th><th /></tr></thead>
            <tbody>{history.data.map((j) => <tr key={j.id}><td className="tabular text-[12px]">{fmtDateTime(j.created_at)}</td><td className="text-[12px]">{j.importer}</td>
              <td className="text-[12px]">{j.filename}{j.reprocess_of_id && " ↻"}</td>
              <td><ToneBadge tone={IMPORT_TONE[j.status]}>{t(`int.st.${j.status}` as "int.st.VALIDATED")}</ToneBadge></td>
              <td className="tabular text-[12px]">{j.total_rows} / {j.error_count}</td>
              <td><Button variant="ghost" onClick={() => setJob(j)}>{t("common.view")}</Button></td></tr>)}</tbody></table>
        )}
      </Card>
    </div>
  );
}

function ApiClients() {
  const { t, fmtDateTime } = useI18n();
  const { can } = useAuth();
  const plants = usePlants();
  const list = useResource(() => api.get<ApiClientRow[]>("/integrations/api-clients"));
  const [creating, setCreating] = useState<Record<string, string> | null>(null);
  const [created, setCreated] = useState<ApiClientRow | null>(null);
  const [revoking, setRevoking] = useState<ApiClientRow | null>(null);
  const { busy, error, run } = useAction();
  return (
    <Card title={t("int.tab.api")} flush actions={can("integrations:manage") && <Button variant="primary" onClick={() => setCreating({ role_code: "viewer" })}>+ {t("int.newClient")}</Button>}>
      {created?.api_key && <div className="p-3"><Alert tone="warn">{t("int.keyOnce")}<div className="mt-1 break-all font-mono text-[12px]">{created.api_key}</div></Alert></div>}
      {!list.data?.length ? <EmptyState>—</EmptyState> : (
        <table className="data-table"><thead><tr><th>{t("common.name")}</th><th>{t("int.prefix")}</th><th>{t("int.lastUsed")}</th><th>{t("common.status")}</th><th /></tr></thead>
          <tbody>{list.data.map((c) => <tr key={c.id}><td>{c.name}</td><td className="font-mono text-[12px]">gtk_{c.key_prefix}_…</td>
            <td className="tabular text-[12px]">{fmtDateTime(c.last_used_at)}</td>
            <td>{c.revoked_at ? <ToneBadge tone="mute">{t("int.revoke")}</ToneBadge> : <ToneBadge tone="ok">{t("common.active")}</ToneBadge>}</td>
            <td>{!c.revoked_at && can("integrations:manage") && <Button variant="ghost" onClick={() => setRevoking(c)}>{t("int.revoke")}</Button>}</td></tr>)}</tbody></table>
      )}
      <Modal open={!!creating} title={t("int.newClient")} onClose={() => setCreating(null)}
        footer={<Button variant="primary" disabled={!creating?.name || !!busy} onClick={() => creating && run("c", async () => {
          setCreated(await api.post<ApiClientRow>("/integrations/api-clients", { name: creating.name, role_code: creating.role_code,
            plant_ids: creating.plant_id ? [creating.plant_id] : [] }));
        }, () => { setCreating(null); list.reload(); })}>{t("common.create")}</Button>}>
        {error && <Alert>{error}</Alert>}
        {creating && <div className="grid gap-3">
          <Field label={t("common.name")} required><Input value={creating.name ?? ""} onChange={(e) => setCreating({ ...creating, name: e.target.value })} /></Field>
          <Field label={t("int.role")}><Select value={creating.role_code} onChange={(e) => setCreating({ ...creating, role_code: e.target.value })}>
            {["viewer", "auditor", "requester", "metrology_technician", "lab_technician", "edge_agent"].map((r) => <option key={r} value={r}>{r}</option>)}</Select></Field>
          <Field label={t("gage.field.plant")}><Select value={creating.plant_id ?? ""} onChange={(e) => setCreating({ ...creating, plant_id: e.target.value })}>
            <option value="">{t("common.all")}</option>{plants.map((p) => <option key={p.id} value={p.id}>{p.code}</option>)}</Select></Field>
        </div>}
      </Modal>
      <ReasonDialog open={!!revoking} title={t("int.revoke")} label={t("common.reason")} danger onClose={() => setRevoking(null)}
        onConfirm={(reason) => run("r", () => api.post(`/integrations/api-clients/${revoking!.id}/revoke`, { reason }), () => { setRevoking(null); list.reload(); })} />
    </Card>
  );
}

function Webhooks() {
  const { t, fmtDateTime } = useI18n();
  const { can } = useAuth();
  const list = useResource(() => api.get<Webhook[]>("/integrations/webhooks"));
  const types = useResource(() => api.get<string[]>("/integrations/event-types"));
  const deliveries = useResource(() => api.get<Delivery[]>("/integrations/webhook-deliveries"));
  const [creating, setCreating] = useState<{ name: string; url: string; events: string[] } | null>(null);
  const [created, setCreated] = useState<Webhook | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [lastError, setLastError] = useState<unknown>(null);
  const { busy, error, run } = useAction();
  return (
    <div className="space-y-4">
      <Card title={t("int.tab.webhooks")} flush actions={can("integrations:manage") && <>
        <Button disabled={!!busy} onClick={() => run("d", async () => {
          const r = await api.post<Record<string, number>>("/integrations/webhooks/dispatch");
          setResult(Object.entries(r).map(([k, v]) => `${k}: ${v}`).join(" · "));
        }, deliveries.reload)}>{t("int.dispatch")}</Button>
        <Button variant="primary" onClick={() => setCreating({ name: "", url: "https://", events: [] })}>+ {t("int.newWebhook")}</Button></>}>
        {created?.secret && <div className="p-3"><Alert tone="warn">{t("int.secretOnce")}<div className="mt-1 break-all font-mono text-[12px]">{created.secret}</div></Alert></div>}
        {result && <div className="p-3"><Alert tone="info">{result}</Alert></div>}
        {!list.data?.length ? <EmptyState>—</EmptyState> : (
          <table className="data-table"><thead><tr><th>{t("common.name")}</th><th>{t("int.url")}</th><th>{t("int.events")}</th><th>{t("common.status")}</th></tr></thead>
            <tbody>{list.data.map((w) => <tr key={w.id}><td>{w.name}</td><td className="font-mono text-[12px]">{w.url}</td>
              <td className="text-[11px]">{w.event_types.join(", ")}</td><td><ToneBadge tone={w.is_active ? "ok" : "mute"}>{w.is_active ? t("common.active") : t("common.inactive")}</ToneBadge></td></tr>)}</tbody></table>
        )}
      </Card>
      <Card title={t("int.deliveries")} flush>
        {!deliveries.data?.length ? <EmptyState>—</EmptyState> : (
          <table className="data-table"><thead><tr><th>{t("common.date")}</th><th>{t("int.events")}</th><th>{t("common.status")}</th><th>{t("int.attempts")}</th><th>HTTP</th><th /></tr></thead>
            <tbody>{deliveries.data.map((d) => <tr key={d.id}><td className="tabular text-[12px]">{fmtDateTime(d.created_at)}</td><td className="text-[12px]">{d.event_type}</td>
              <td><ToneBadge tone={DELIVERY_TONE[d.status]}>{d.status}</ToneBadge></td><td className="tabular">{d.attempts}</td>
              <td className="text-[12px]">{d.last_status_code ?? d.last_error ?? "—"}</td>
              <td>{d.status !== "SUCCEEDED" && can("integrations:manage") && <Button variant="ghost" onClick={() => run("rt", () => api.post(`/integrations/webhook-deliveries/${d.id}/retry`), deliveries.reload)}>{t("int.retry")}</Button>}</td></tr>)}</tbody></table>
        )}
      </Card>
      <Modal open={!!creating} title={t("int.newWebhook")} onClose={() => setCreating(null)}
        footer={<Button variant="primary" disabled={!creating?.name || !creating.events.length || !!busy} onClick={() => creating && run("c", async () => {
          setLastError(null);
          try { setCreated(await api.post<Webhook>("/integrations/webhooks", { name: creating.name, url: creating.url, event_types: creating.events })); }
          catch (e) { setLastError(e); throw e; }
        }, () => { setCreating(null); list.reload(); })}>{t("common.create")}</Button>}>
        {error && <Alert>{error}<IssueList error={lastError} /></Alert>}
        {creating && <div className="grid gap-3">
          <Field label={t("common.name")} required><Input value={creating.name} onChange={(e) => setCreating({ ...creating, name: e.target.value })} /></Field>
          <Field label={t("int.url")} required><Input value={creating.url} onChange={(e) => setCreating({ ...creating, url: e.target.value })} /></Field>
          <div className="grid gap-1 sm:grid-cols-2">{(types.data ?? []).map((ev) => <Check key={ev} label={ev} checked={creating.events.includes(ev)}
            onChange={(c) => setCreating({ ...creating, events: c ? [...creating.events, ev] : creating.events.filter((x) => x !== ev) })} />)}</div>
        </div>}
      </Modal>
    </div>
  );
}

function Devices() {
  const { t, fmtDateTime } = useI18n();
  const { can } = useAuth();
  const plants = usePlants();
  const gages = useGages();
  const list = useResource(() => api.get<Device[]>("/integrations/devices"));
  const adapters = useResource(() => api.get<{ adapters: AdapterInfo[]; planned_not_supported: string[] }>("/integrations/adapters"));
  const [sel, setSel] = useState<string | null>(null);
  const readings = useResource(() => (sel ? api.get<Reading[]>(`/integrations/devices/${sel}/readings`) : Promise.resolve([])), [sel]);
  const [creating, setCreating] = useState<Record<string, string> | null>(null);
  const [sim, setSim] = useState({ nominal: "10", sigma: "0.002", count: "10" });
  const [msg, setMsg] = useState<string | null>(null);
  const { busy, error, run } = useAction();
  const device = list.data?.find((d) => d.id === sel);
  return (
    <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
      <div className="space-y-4">
        <Card title={t("int.tab.devices")} flush actions={can("integrations:manage") && <Button variant="primary" onClick={() => setCreating({ adapter: "simulator" })}>+ {t("int.newDevice")}</Button>}>
          {error && <div className="p-3"><Alert>{error}</Alert></div>}
          {!list.data?.length ? <EmptyState>—</EmptyState> : (
            <table className="data-table"><thead><tr><th>{t("int.deviceCode")}</th><th>{t("common.name")}</th><th>{t("int.adapter")}</th><th>{t("msa.gage")}</th></tr></thead>
              <tbody>{list.data.map((d) => <tr key={d.id} className={d.id === sel ? "bg-accent/5" : ""} onClick={() => setSel(d.id)}>
                <td className="cursor-pointer font-mono text-[12px] text-accent">{d.device_code}</td><td>{d.name}</td><td className="text-[12px]">{d.adapter}</td>
                <td className="font-mono text-[12px]">{gages.find((g) => g.id === d.gage_id)?.gage_code ?? "—"}</td></tr>)}</tbody></table>
          )}
        </Card>
        {device && (
          <Card title={`${t("int.readings")} · ${device.device_code}`} flush actions={device.adapter === "simulator" && can("integrations:manage") && (
            <div className="flex items-end gap-1">
              <Input aria-label={t("int.nominal")} className="w-20" value={sim.nominal} onChange={(e) => setSim({ ...sim, nominal: e.target.value })} />
              <Input aria-label={t("int.sigma")} className="w-20" value={sim.sigma} onChange={(e) => setSim({ ...sim, sigma: e.target.value })} />
              <Input aria-label={t("int.count")} className="w-16" value={sim.count} onChange={(e) => setSim({ ...sim, count: e.target.value })} />
              <Button disabled={!!busy} onClick={() => run("s", async () => {
                const r = await api.post<{ accepted: number; warnings: string[] }>(`/integrations/devices/${device.id}/simulate`,
                  { nominal: Number(sim.nominal), sigma: Number(sim.sigma), count: Number(sim.count) });
                setMsg(`+${r.accepted} ${r.warnings.join(" ")}`);
              }, readings.reload)}>{t("int.simulate")}</Button>
            </div>)}>
            {msg && <div className="p-3"><Alert tone="info">{msg}</Alert></div>}
            {!readings.data?.length ? <EmptyState>—</EmptyState> : (
              <div className="max-h-80 overflow-auto"><table className="data-table"><thead><tr><th>{t("common.date")}</th><th>Valor</th><th>Raw</th><th>{t("common.status")}</th></tr></thead>
                <tbody>{readings.data.map((r) => <tr key={r.id}><td className="tabular text-[12px]">{fmtDateTime(r.captured_at)}</td>
                  <td className="tabular">{r.value} {r.unit}</td><td className="font-mono text-[11px]">{r.raw}</td><td className="text-[11px]">{r.gage_status ?? "—"}</td></tr>)}</tbody></table></div>
            )}
          </Card>
        )}
      </div>
      <Card title={t("int.adapter")}>
        {!adapters.data ? <Loading /> : <>
          <ul className="space-y-2 text-[13px]">{adapters.data.adapters.map((a) => <li key={a.code}><b>{a.name}</b> <ToneBadge tone="ok">{a.status}</ToneBadge>
            <div className="text-[12px] text-ink-3">{a.description}</div></li>)}</ul>
          <div className="mt-3 text-[11px] font-semibold uppercase text-ink-3">{t("int.planned")}</div>
          <ul className="list-disc pl-5 text-[12px] text-ink-3">{adapters.data.planned_not_supported.map((p) => <li key={p}>{p}</li>)}</ul>
        </>}
      </Card>
      <Modal open={!!creating} title={t("int.newDevice")} onClose={() => setCreating(null)}
        footer={<Button variant="primary" disabled={!creating?.device_code || !creating?.name || !!busy} onClick={() => creating && run("c", () => api.post("/integrations/devices", {
          device_code: creating.device_code, name: creating.name, adapter: creating.adapter, plant_id: creating.plant_id || plants[0]?.id,
          gage_id: creating.gage_id || null, serial_number: creating.serial_number || null }), () => { setCreating(null); list.reload(); })}>{t("common.create")}</Button>}>
        {error && <Alert>{error}</Alert>}
        {creating && <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("int.deviceCode")} required><Input value={creating.device_code ?? ""} onChange={(e) => setCreating({ ...creating, device_code: e.target.value })} /></Field>
          <Field label={t("common.name")} required><Input value={creating.name ?? ""} onChange={(e) => setCreating({ ...creating, name: e.target.value })} /></Field>
          <Field label={t("int.adapter")}><Select value={creating.adapter} onChange={(e) => setCreating({ ...creating, adapter: e.target.value })}>
            {(adapters.data?.adapters ?? []).map((a) => <option key={a.code} value={a.code}>{a.name}</option>)}</Select></Field>
          <Field label={t("msa.gage")}><Select value={creating.gage_id ?? ""} onChange={(e) => setCreating({ ...creating, gage_id: e.target.value })}>
            <option value="">—</option>{gages.map((g) => <option key={g.id} value={g.id}>{g.gage_code}</option>)}</Select></Field>
          <Field label={t("gage.field.plant")}><Select value={creating.plant_id ?? plants[0]?.id ?? ""} onChange={(e) => setCreating({ ...creating, plant_id: e.target.value })}>
            {plants.map((p) => <option key={p.id} value={p.id}>{p.code}</option>)}</Select></Field>
        </div>}
      </Modal>
    </div>
  );
}

function Events() {
  const { t, fmtDateTime } = useI18n();
  const list = useResource(() => api.get<{ id: string; event_type: string; entity_type: string; payload: { data: Record<string, unknown> }; created_at: string }[]>("/integrations/events"));
  if (!list.data) return <Loading />;
  return (
    <Card flush title={t("int.tab.events")}>
      {!list.data.length ? <EmptyState>—</EmptyState> : (
        <table className="data-table"><thead><tr><th>{t("common.date")}</th><th>{t("int.events")}</th><th>Data</th></tr></thead>
          <tbody>{list.data.map((e) => <tr key={e.id}><td className="tabular text-[12px]">{fmtDateTime(e.created_at)}</td><td className="text-[12px]">{e.event_type}</td>
            <td className="max-w-[520px] truncate font-mono text-[11px]">{JSON.stringify(e.payload.data)}</td></tr>)}</tbody></table>
      )}
    </Card>
  );
}
