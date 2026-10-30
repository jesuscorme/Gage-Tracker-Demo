"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  Alert, Button, Card, Check, EmptyState, ErrorState, Field, Input, Loading, Modal, PageHeader, Select, Textarea, ToneBadge, useAction,
} from "@/components/ui";
import { IssueList } from "@/components/workflow";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { localToday, useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { useGages, useUsers } from "@/lib/lookups";
import type { OotCase } from "@/lib/types-b3";

export default function OotListPage() {
  const { t, fmtDate } = useI18n();
  const { can } = useAuth();
  const [openOnly, setOpenOnly] = useState(true);
  const [creating, setCreating] = useState(false);
  const list = useResource(() => api.get<OotCase[]>("/oot/cases", { open_only: openOnly }), [openOnly]);
  return (
    <>
      <PageHeader title={t("oot.title")} actions={can("oot:manage") && <Button variant="primary" onClick={() => setCreating(true)}>+ {t("oot.new")}</Button>} />
      <Card flush actions={<Check label={t("oot.openOnly")} checked={openOnly} onChange={setOpenOnly} />} title=" ">
        {list.error ? <div className="px-4"><ErrorState error={list.error} onRetry={list.reload} /></div>
          : !list.data ? <div className="px-4"><Loading /></div>
          : list.data.length === 0 ? <EmptyState>{t("oot.empty")}</EmptyState> : (
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead><tr><th>{t("oot.code")}</th><th>{t("msa.gage")}</th><th>{t("oot.detected")}</th><th className="hidden md:table-cell">{t("oot.source")}</th>
                  <th className="hidden md:table-cell">{t("oot.deviation")}</th><th>{t("common.status")}</th><th>{t("oot.restriction")}</th></tr></thead>
                <tbody>
                  {list.data.map((c) => (
                    <tr key={c.id}>
                      <td><Link href={`/oot/${c.id}`} className="font-mono text-[13px] font-semibold text-accent hover:underline">{c.case_code}</Link></td>
                      <td><div className="font-mono text-[12px]">{c.gage_code}</div><div className="truncate text-[11px] text-ink-3">{c.gage_description}</div></td>
                      <td className="tabular">{fmtDate(c.detected_on)}</td>
                      <td className="hidden text-[12px] md:table-cell">{t(`oot.src.${c.detection_source}` as "oot.src.MANUAL")}</td>
                      <td className="hidden tabular md:table-cell">{c.max_deviation ?? "—"}</td>
                      <td><ToneBadge tone={c.status === "CLOSED" ? "ok" : c.status === "CANCELLED" ? "mute" : "warn"}>{c.status}</ToneBadge></td>
                      <td>{c.restriction_applied && !c.gage_released_at ? <ToneBadge tone="bad">{c.gage_control_status}</ToneBadge> : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </Card>
      <NewCase open={creating} onClose={() => setCreating(false)} />
    </>
  );
}

function NewCase({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const { me } = useAuth();
  const router = useRouter();
  const gages = useGages();
  const users = useUsers();
  const [f, setF] = useState<Record<string, string>>({ detected_on: localToday() });
  const [lastError, setLastError] = useState<unknown>(null);
  const { busy, error, run } = useAction();
  const set = (k: string, v: string) => setF({ ...f, [k]: v });
  return (
    <Modal open={open} title={t("oot.new")} onClose={onClose}
      footer={<Button variant="primary" disabled={!!busy || !f.gage_id || !f.description} onClick={() => run("c", async () => {
        setLastError(null);
        try {
          const c = await api.post<OotCase>("/oot/cases", { gage_id: f.gage_id, detected_on: f.detected_on, description: f.description,
            responsible_id: f.responsible_id || me?.id, found_result: f.found_result || null, tolerance: f.tolerance || null,
            max_deviation: f.max_deviation || null });
          router.push(`/oot/${c.id}`);
        } catch (e) { setLastError(e); throw e; }
      })}>{t("common.create")}</Button>}>
      {error && <Alert>{error}<IssueList error={lastError} /></Alert>}
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("msa.gage")} required><Select value={f.gage_id ?? ""} onChange={(e) => set("gage_id", e.target.value)}>
          <option value="">—</option>{gages.map((g) => <option key={g.id} value={g.id}>{g.gage_code} · {g.description}</option>)}</Select></Field>
        <Field label={t("oot.detected")} required><Input type="date" value={f.detected_on} onChange={(e) => set("detected_on", e.target.value)} /></Field>
        <Field label={t("msa.responsible")}><Select value={f.responsible_id ?? me?.id ?? ""} onChange={(e) => set("responsible_id", e.target.value)}>
          {users.list.map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}</Select></Field>
        <Field label={t("oot.deviation")}><Input inputMode="decimal" value={f.max_deviation ?? ""} onChange={(e) => set("max_deviation", e.target.value)} /></Field>
        <Field label={t("oot.found")}><Input value={f.found_result ?? ""} onChange={(e) => set("found_result", e.target.value)} /></Field>
        <Field label={t("oot.tolerance")}><Input value={f.tolerance ?? ""} onChange={(e) => set("tolerance", e.target.value)} /></Field>
      </div>
      <Field label={t("oot.description")} required className="mt-3"><Textarea value={f.description ?? ""} onChange={(e) => set("description", e.target.value)} /></Field>
    </Modal>
  );
}
