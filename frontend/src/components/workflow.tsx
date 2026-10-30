"use client";

import { useState } from "react";
import { ApiError, api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import type { Issue, WorkflowState } from "@/lib/types-b3";
import { Alert, Button, Card, Field, Loading, Modal, Textarea, ToneBadge, useAction } from "./ui";

/** Shows business-rule details (lists of issues or messages) returned by the API. */
export function IssueList({ error }: { error: unknown }) {
  const { t } = useI18n();
  if (!(error instanceof ApiError) || !error.details) return null;
  const d = error.details as unknown;
  const items: string[] = Array.isArray(d)
    ? d.map((x) => (typeof x === "string" ? x
      : (x as Issue).message ? `${(x as Issue).row ? `${t("issues.row", { n: (x as Issue).row! })}: ` : ""}${(x as Issue).message}`
      : (x as { message?: string; rule?: string }).rule ? `${(x as { rule: string }).rule}: ${(x as { message: string }).message}`
      : JSON.stringify(x)))
    : typeof d === "object" ? Object.entries(d as Record<string, unknown>).map(([k, v]) => `${k}: ${typeof v === "string" ? v : JSON.stringify(v)}`)
    : [];
  if (!items.length) return null;
  return (
    <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[12px]">
      {items.slice(0, 30).map((m, i) => <li key={i}>{m}</li>)}
    </ul>
  );
}

/** Generic workflow panel: current state, available transitions (with reasons) and history. */
export function WorkflowPanel({ entity, id, onChange, users }: {
  entity: "msa_study" | "oot_case"; id: string; onChange?: () => void; users?: Record<string, string>;
}) {
  const { t, fmtDateTime } = useI18n();
  const wf = useResource(() => api.get<WorkflowState>(`/workflows/${entity}/${id}`), [entity, id]);
  const [pending, setPending] = useState<{ code: string; label: string; needs: boolean } | null>(null);
  const [comment, setComment] = useState("");
  const [lastError, setLastError] = useState<unknown>(null);
  const { busy, error, run, setError } = useAction();

  const go = async (code: string, c: string | null) => {
    setLastError(null);
    const ok = await run(code, async () => {
      try {
        await api.post(`/workflows/${entity}/${id}/transitions`, { transition: code, comment: c || null });
      } catch (e) {
        setLastError(e);
        throw e;
      }
    });
    if (ok) {
      setPending(null);
      setComment("");
      wf.reload();
      onChange?.();
    }
  };
  if (!wf.data) return <Card title={t("wf.title")}><Loading /></Card>;
  const label = (code: string | null) => wf.data!.states.find((s) => s.code === code)?.label ?? code ?? "—";
  return (
    <Card title={t("wf.title")}>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="text-[12px] text-ink-3">{t("wf.state")}</span>
        <ToneBadge tone="info">{label(wf.data.state)}</ToneBadge>
        <span className="text-[11px] text-ink-3">{t("wf.version")}: {wf.data.version === 0 ? "sistema" : `v${wf.data.version}`}</span>
      </div>
      {error && <Alert>{error}<IssueList error={lastError} /></Alert>}
      {wf.data.transitions.length === 0 ? <p className="text-[13px] text-ink-3">{t("wf.noTransitions")}</p> : (
        <div className="flex flex-wrap gap-2">
          {wf.data.transitions.map((tr) => (
            <div key={tr.code} className="flex flex-col">
              <Button variant={tr.action === "APPROVE" ? "primary" : "secondary"} disabled={!tr.allowed || !!busy}
                title={tr.reason ?? undefined}
                onClick={() => (tr.require_comment ? setPending({ code: tr.code, label: tr.label, needs: true })
                  : go(tr.code, null))}>
                {tr.label}
              </Button>
              {tr.approvals_required > 1 && <span className="mt-0.5 text-[11px] text-ink-3">{t("wf.votes", { n: tr.votes, m: tr.approvals_required })}</span>}
              {!tr.allowed && tr.reason && <span className="mt-0.5 max-w-[220px] text-[11px] text-ink-3">{tr.reason}</span>}
            </div>
          ))}
        </div>
      )}
      <details className="mt-4">
        <summary className="cursor-pointer text-[12px] font-semibold text-ink-2">{t("wf.history")} ({wf.data.history.length})</summary>
        <ol className="mt-2 space-y-1.5 text-[12px]">
          {wf.data.history.map((e, i) => (
            <li key={i} className="border-l-2 border-line pl-2">
              <span className="font-semibold">{t(`wf.event.${e.event_type}` as "wf.event.CREATED")}</span>
              {e.to_state && <> → {label(e.to_state)}</>} {e.transition === "SYSTEM" && <span className="text-ink-3">({t("wf.system")})</span>}
              <span className="text-ink-3"> · {fmtDateTime(e.occurred_at)}{e.actor_id && users?.[e.actor_id] ? ` · ${users[e.actor_id]}` : ""}</span>
              {e.comment && <div className="text-ink-2">“{e.comment}”</div>}
            </li>
          ))}
        </ol>
      </details>
      <Modal open={!!pending} title={pending?.label ?? ""} onClose={() => { setPending(null); setError(null); }}
        footer={<Button variant="primary" disabled={!comment.trim() || !!busy} onClick={() => pending && go(pending.code, comment)}>{pending?.label}</Button>}>
        {error && <Alert>{error}<IssueList error={lastError} /></Alert>}
        <Field label={t("wf.comment")} required>
          <Textarea autoFocus value={comment} onChange={(e) => setComment(e.target.value)} maxLength={2000} />
        </Field>
      </Modal>
    </Card>
  );
}
