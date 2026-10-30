"use client";

import { useState } from "react";
import { Icon } from "@/components/icons";
import { Alert, Button, Card, FileInput, LinkButton, PageHeader, useAction } from "@/components/ui";
import { api, form } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import type { ImportResult } from "@/lib/types";

export default function ImportGagesPage() {
  const { t } = useI18n();
  const { can } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const { busy, error, run } = useAction();

  if (!can("gages:import")) return <Alert>{t("common.forbidden")}</Alert>;

  const send = (dry: boolean) =>
    run(dry ? "dry" : "run", async () => {
      setResult(await api.post<ImportResult>("/gages/import", form({ file }), { dry_run: dry }));
    });

  return (
    <>
      <PageHeader eyebrow={t("gages.title")} title={t("gage.import.title")}
        actions={<LinkButton href="/gages">{t("common.cancel")}</LinkButton>} />
      <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
        <Card>
          <p className="text-[13px] text-ink-2">{t("gage.import.help")}</p>
          <Button className="mt-3" onClick={() => api.download("/gages/import/template")}>
            <Icon name="download" size={14} /> {t("gage.import.template")}
          </Button>
          <div className="mt-5 space-y-3 border-t border-line pt-4">
            <FileInput accept=".csv,.xlsx" onFile={(f) => { setFile(f); setResult(null); }} label="CSV / XLSX" />
            <div className="flex gap-2">
              <Button disabled={!file} loading={busy === "dry"} onClick={() => send(true)}>{t("gage.import.validate")}</Button>
              <Button variant="primary" disabled={!file || !result || !result.dry_run || result.errors.length > 0}
                loading={busy === "run"} onClick={() => send(false)}>
                {t("gage.import.run")}
              </Button>
            </div>
            {error && <Alert>{error}</Alert>}
          </div>
        </Card>
        <Card flush title={t("common.result")}>
          {!result ? (
            <p className="px-4 py-6 text-[13px] text-ink-3">—</p>
          ) : (
            <div>
              <div className="px-4 py-3">
                {result.created > 0 ? (
                  <Alert tone="ok">{t("gage.import.created", { n: result.created })}</Alert>
                ) : (
                  <Alert tone={result.errors.length ? "bad" : "ok"}>
                    {t("gage.import.valid", { n: result.valid_rows, total: result.total_rows })}
                  </Alert>
                )}
              </div>
              {result.errors.length > 0 && (
                <table className="data-table">
                  <thead><tr><th>{t("gage.import.row")}</th><th>Gage ID</th><th>Error</th></tr></thead>
                  <tbody>
                    {result.errors.map((e) => (
                      <tr key={e.row}>
                        <td className="tabular">{e.row}</td>
                        <td className="font-mono">{e.gage_code ?? "—"}</td>
                        <td className="text-[12px] text-bad">{e.errors.join(" · ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
