"use client";

import { useState } from "react";
import { Alert, Button, Card, EmptyState, Input, Loading, PageHeader, Select, Spec, Tabs, ToneBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { useGages } from "@/lib/lookups";
import { COMPLIANCE_TONE } from "@/lib/status-b3";
import type { ComplianceMatrix } from "@/lib/types-b3";

type Tab = "matrix" | "pending" | "approvals" | "certificates" | "dossier";
type Row = Record<string, unknown>;

const cell = (v: unknown) => (v === null || v === undefined ? "—" : typeof v === "object" ? JSON.stringify(v) : String(v));

function RowsTable({ rows }: { rows: Row[] }) {
  if (!rows.length) return <EmptyState>—</EmptyState>;
  const keys = Object.keys(rows[0]);
  return (
    <div className="overflow-x-auto"><table className="data-table">
      <thead><tr>{keys.map((k) => <th key={k}>{k}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => <tr key={i}>{keys.map((k) => <td key={k} className="max-w-[360px] truncate text-[12px]">{cell(r[k])}</td>)}</tr>)}</tbody>
    </table></div>
  );
}

export default function CompliancePage() {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("matrix");
  const matrix = useResource(() => api.get<ComplianceMatrix>("/compliance/matrix"));
  return (
    <>
      <PageHeader title={t("cmp.title")} actions={<Button onClick={() => api.download("/compliance/export.xlsx")}>{t("cmp.export")}</Button>} />
      {matrix.data && <Alert tone="info"><b>{t("cmp.disclaimer")}:</b> {matrix.data.disclaimer}</Alert>}
      <div className="mt-3" />
      <Tabs value={tab} onChange={setTab} items={(["matrix", "pending", "approvals", "certificates", "dossier"] as const).map((v) => ({ value: v, label: t(`cmp.tab.${v}`) }))} />
      <div className="mt-4 space-y-4">
        {tab === "matrix" && (!matrix.data ? <Loading /> : <MatrixView m={matrix.data} />)}
        {tab === "pending" && <PendingView />}
        {tab === "approvals" && <ApprovalsView />}
        {tab === "certificates" && <CertificatesView />}
        {tab === "dossier" && <DossierView />}
      </div>
    </>
  );
}

function MatrixView({ m }: { m: ComplianceMatrix }) {
  const { t } = useI18n();
  return (
    <>
      <div className="grid gap-3 lg:grid-cols-2">
        {m.processes.map((p) => (
          <Card key={p.process} title={p.description} actions={<ToneBadge tone={COMPLIANCE_TONE[p.state]}>{t(`cmp.st.${p.state}` as "cmp.st.ATTENTION")}</ToneBadge>}>
            <p className="text-[11px] text-ink-3">{t("cmp.clauses")}: {p.clauses.join(" · ") || "—"}</p>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              <div><div className="text-[11px] font-semibold uppercase text-ink-3">{t("cmp.evidence")}</div>
                <ul className="text-[12px]">{Object.entries(p.evidence).map(([k, v]) => <li key={k}>{k}: <b>{v}</b></li>)}</ul></div>
              <div><div className="text-[11px] font-semibold uppercase text-ink-3">{t("cmp.gaps")}</div>
                <ul className="text-[12px]">{Object.entries(p.gaps).map(([k, v]) => <li key={k} className={v ? "text-warn" : ""}>{k}: <b>{v}</b></li>)}</ul></div>
            </div>
          </Card>
        ))}
      </div>
      <Card title={t("cmp.clauses")} flush>
        <table className="data-table"><thead><tr><th>Standard</th><th>Clause</th><th>{t("common.title")}</th><th>{t("cmp.process")}</th><th>{t("common.status")}</th></tr></thead>
          <tbody>{m.clauses.map((c) => <tr key={c.standard + c.clause}><td className="text-[12px]">{c.standard}</td><td className="font-mono text-[12px]">{c.clause}</td>
            <td className="text-[12px]">{c.title}</td><td className="text-[11px]">{c.processes.join(", ")}</td>
            <td><ToneBadge tone={COMPLIANCE_TONE[c.state]}>{t(`cmp.st.${c.state}` as "cmp.st.ATTENTION")}</ToneBadge></td></tr>)}</tbody></table>
      </Card>
    </>
  );
}

function PendingView() {
  const p = useResource(() => api.get<Record<string, Row[]>>("/compliance/pending"));
  if (!p.data) return <Loading />;
  return <div className="grid gap-3 lg:grid-cols-2">{Object.entries(p.data).map(([k, rows]) => (
    <Card key={k} title={`${k} (${rows.length})`} flush><RowsTable rows={rows} /></Card>))}</div>;
}

function ApprovalsView() {
  const { t } = useI18n();
  const a = useResource(() => api.get<Row[]>("/compliance/approvals"));
  return <Card title={t("cmp.tab.approvals")} flush>{!a.data ? <Loading /> : <RowsTable rows={a.data} />}</Card>;
}

function CertificatesView() {
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const list = useResource(() => api.get<Row[]>("/compliance/certificates", { q }), [q]);
  return (
    <Card title={t("cmp.tab.certificates")} flush>
      <div className="border-b border-line p-3"><Input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("common.search")} /></div>
      {!list.data ? <Loading /> : (
        <div className="overflow-x-auto"><table className="data-table"><thead><tr><th>{t("cmp.kind")}</th><th>{t("cmp.subject")}</th><th>No.</th><th>{t("cmp.issuer")}</th><th>{t("common.date")}</th><th /></tr></thead>
          <tbody>{list.data.map((c, i) => <tr key={i}><td className="text-[12px]">{cell(c.kind)}</td><td className="font-mono text-[12px]">{cell(c.subject)}</td>
            <td className="font-mono text-[12px]">{cell(c.certificate_number)}</td><td className="text-[12px]">{cell(c.issuer)}</td><td className="text-[12px]">{cell(c.issue_date)}</td>
            <td><Button variant="ghost" onClick={() => api.download(`/attachments/${c.attachment_id}/download`, undefined, { open: true })}>{t("common.open")}</Button></td></tr>)}</tbody></table></div>
      )}
    </Card>
  );
}

function DossierView() {
  const { t } = useI18n();
  const gages = useGages();
  const [gage, setGage] = useState("");
  const d = useResource(() => (gage ? api.get<Record<string, Row[] | Row>>(`/compliance/gages/${gage}/dossier`) : Promise.resolve(null)), [gage]);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <Select value={gage} onChange={(e) => setGage(e.target.value)} className="w-auto" aria-label={t("cmp.selectGage")}>
          <option value="">{t("cmp.selectGage")}</option>{gages.map((g) => <option key={g.id} value={g.id}>{g.gage_code} · {g.description}</option>)}</Select>
        {gage && <Button onClick={() => api.download("/compliance/export.xlsx", { gage_id: gage })}>{t("cmp.export")}</Button>}
      </div>
      {gage && !d.data && <Loading />}
      {d.data && <>
        <Card title={t("common.general")}><div className="grid gap-2 sm:grid-cols-4">
          {Object.entries(d.data.gage as Row).map(([k, v]) => <Spec key={k} label={k}>{cell(v)}</Spec>)}</div></Card>
        {(["calibrations", "certificates", "oot_cases", "msa_studies", "status_history", "movements", "documents", "audit_trail"] as const).map((k) => (
          <Card key={k} title={`${k} (${(d.data![k] as Row[]).length})`} flush><RowsTable rows={d.data![k] as Row[]} /></Card>))}
      </>}
    </div>
  );
}
