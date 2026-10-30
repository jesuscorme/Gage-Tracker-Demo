"use client";

import { useState } from "react";
import { api, form } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import type { Attachment } from "@/lib/types";
import { Icon } from "./icons";
import { Alert, Button, Card, FileInput, Input, ReasonDialog, Select, useAction } from "./ui";

const CATEGORIES = ["DOCUMENT", "PHOTO", "EVIDENCE"] as const;

function size(n: number) {
  return n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`;
}

/** Documents of a record: list, open/download, upload and withdraw (with reason). */
export function DocumentsPanel({ entityType, entityId, canUpload, title }: {
  entityType: string;
  entityId: string;
  canUpload: boolean;
  title?: string;
}) {
  const { t, fmtDateTime } = useI18n();
  const docs = useResource(() => api.get<Attachment[]>("/attachments", { entity_type: entityType, entity_id: entityId }), [entityId]);
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState<(typeof CATEGORIES)[number]>("DOCUMENT");
  const [docTitle, setDocTitle] = useState("");
  const [removing, setRemoving] = useState<Attachment | null>(null);
  const [inputKey, setInputKey] = useState(0);
  const { busy, error, run } = useAction();

  const upload = () =>
    run("upload", () =>
      api.post("/attachments", form({ entity_type: entityType, entity_id: entityId, category, title: docTitle, file })),
    () => {
      setFile(null);
      setDocTitle("");
      setInputKey((k) => k + 1);
      docs.reload();
    });

  return (
    <Card flush title={title ?? t("common.documents")}>
      {error && <div className="px-4 pt-3"><Alert>{error}</Alert></div>}
      {docs.data?.length ? (
        <ul className="divide-y divide-line-2">
          {docs.data.map((d) => (
            <li key={d.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
              {d.content_type.startsWith("image/") ? (
                <span className="grid size-9 place-items-center rounded bg-info-soft text-info"><Icon name="file" size={16} /></span>
              ) : (
                <span className="grid size-9 place-items-center rounded bg-line-2 text-[10px] font-semibold text-ink-2">
                  {d.original_filename.split(".").pop()?.toUpperCase()}
                </span>
              )}
              <div className="min-w-0 flex-1">
                <div className="truncate text-[13px] font-medium">{d.title || d.original_filename}</div>
                <div className="text-[11px] text-ink-3">
                  {t(`doc.${d.category}`)} · {size(d.size_bytes)} · {d.uploaded_by_name} · {fmtDateTime(d.uploaded_at)}
                  {d.is_locked && <> · 🔒 {t("common.locked")}</>}
                </div>
              </div>
              <Button variant="ghost" className="h-7 px-2" onClick={() => run(d.id, () => api.download(`/attachments/${d.id}/download`, undefined, { open: true }))}>
                {t("common.open")}
              </Button>
              <Button variant="ghost" className="h-7 px-2" onClick={() => run(d.id, () => api.download(`/attachments/${d.id}/download`, undefined, { filename: d.original_filename }))}>
                <Icon name="download" size={14} />
              </Button>
              {canUpload && !d.is_locked && (
                <Button variant="ghost" className="h-7 px-2 text-bad" onClick={() => setRemoving(d)}>{t("common.remove")}</Button>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="px-4 py-5 text-[13px] text-ink-3">{docs.loading ? t("common.loading") : t("doc.empty")}</p>
      )}
      {canUpload && (
        <div className="grid gap-2 border-t border-line bg-line-2/40 px-4 py-3 sm:grid-cols-[140px_1fr_1fr_auto] sm:items-center">
          <Select value={category} onChange={(e) => setCategory(e.target.value as (typeof CATEGORIES)[number])} aria-label={t("common.category")}>
            {CATEGORIES.map((c) => <option key={c} value={c}>{t(`doc.${c}`)}</option>)}
          </Select>
          <Input placeholder={t("common.title")} maxLength={200} value={docTitle} onChange={(e) => setDocTitle(e.target.value)} />
          <FileInput key={inputKey} onFile={setFile} label={t("doc.allowed")} accept=".pdf,.png,.jpg,.jpeg,.webp,.xlsx,.csv" />
          <Button variant="primary" disabled={!file} loading={busy === "upload"} onClick={upload}>
            <Icon name="upload" size={14} /> {t("common.upload")}
          </Button>
          <p className="text-[11px] text-ink-3 sm:col-span-4">{t("doc.allowed")}</p>
        </div>
      )}
      <ReasonDialog
        open={!!removing}
        title={`${t("common.remove")} · ${removing?.original_filename ?? ""}`}
        label={t("common.reasonRequired")}
        danger
        onClose={() => setRemoving(null)}
        onConfirm={(reason) => api.post(`/attachments/${removing!.id}/remove`, { reason }).then(docs.reload)}
      />
    </Card>
  );
}
