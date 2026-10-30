"use client";

import { useState } from "react";
import { Alert, Button, Card, EmptyState, ErrorState, Field, Input, Loading, Modal, PageHeader, cx, errorText } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import type { GageType } from "@/lib/types";

const EMPTY = { code: "", name: "", description: "", default_frequency_days: "" };

export default function GageTypesPage() {
  const { t } = useI18n();
  const { can } = useAuth();
  const manage = can("gage_types:manage");
  const types = useResource(() => api.get<GageType[]>("/gage-types", { include_inactive: true }));
  const [editing, setEditing] = useState<GageType | "new" | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function open(gt: GageType | "new") {
    setError(null);
    setEditing(gt);
    setForm(
      gt === "new"
        ? EMPTY
        : { code: gt.code, name: gt.name, description: gt.description ?? "", default_frequency_days: gt.default_frequency_days?.toString() ?? "" },
    );
  }

  async function save() {
    setBusy(true);
    setError(null);
    const body = {
      name: form.name.trim(),
      description: form.description.trim() || null,
      default_frequency_days: form.default_frequency_days ? Number(form.default_frequency_days) : null,
    };
    try {
      if (editing === "new") await api.post("/gage-types", { ...body, code: form.code.trim() });
      else if (editing) await api.patch(`/gage-types/${editing.id}`, body);
      setEditing(null);
      types.reload();
    } catch (err) {
      setError(errorText(t, err));
    } finally {
      setBusy(false);
    }
  }

  async function toggle(gt: GageType) {
    try {
      await api.patch(`/gage-types/${gt.id}`, { is_active: !gt.is_active });
      types.reload();
    } catch (err) {
      setError(errorText(t, err));
    }
  }

  return (
    <>
      <PageHeader
        eyebrow={t("nav.section.admin")}
        title={t("types.title")}
        actions={manage && <Button variant="primary" onClick={() => open("new")}>+ {t("types.new")}</Button>}
      />
      {error && !editing && <div className="mb-3"><Alert>{error}</Alert></div>}
      <Card flush>
        {types.error ? (
          <div className="px-4"><ErrorState error={types.error} onRetry={types.reload} /></div>
        ) : !types.data ? (
          <div className="px-4"><Loading /></div>
        ) : types.data.length === 0 ? (
          <EmptyState action={manage && <Button variant="primary" onClick={() => open("new")}>{t("types.new")}</Button>}>
            {t("types.empty")}
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("common.code")}</th>
                  <th>{t("common.name")}</th>
                  <th className="hidden md:table-cell">{t("common.description")}</th>
                  <th>{t("types.defaultFrequency")}</th>
                  <th>{t("gages.col.status")}</th>
                  {manage && <th className="text-right">{t("common.actions")}</th>}
                </tr>
              </thead>
              <tbody>
                {types.data.map((gt) => (
                  <tr key={gt.id} className={cx(!gt.is_active && "text-ink-3")}>
                    <td className="font-mono font-semibold">{gt.code}</td>
                    <td>{gt.name}</td>
                    <td className="hidden max-w-[360px] truncate text-ink-2 md:table-cell">{gt.description ?? "—"}</td>
                    <td className="tabular">{gt.default_frequency_days ?? "—"}</td>
                    <td>{gt.is_active ? t("common.active") : t("common.inactive")}</td>
                    {manage && (
                      <td className="text-right">
                        <div className="inline-flex gap-1">
                          <Button variant="ghost" className="h-7 px-2" onClick={() => open(gt)}>{t("common.edit")}</Button>
                          <Button variant="ghost" className="h-7 px-2" onClick={() => toggle(gt)}>
                            {gt.is_active ? t("types.deactivate") : t("types.activate")}
                          </Button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Modal
        open={!!editing}
        onClose={() => setEditing(null)}
        title={editing === "new" ? t("types.new") : `${t("common.edit")} · ${editing?.code ?? ""}`}
        footer={
          <>
            <Button onClick={() => setEditing(null)}>{t("common.cancel")}</Button>
            <Button variant="primary" loading={busy} onClick={save} disabled={!form.name.trim() || (editing === "new" && !form.code.trim())}>
              {t("common.save")}
            </Button>
          </>
        }
      >
        {error && <Alert>{error}</Alert>}
        <div className="grid grid-cols-[120px_1fr] gap-3">
          <Field label={t("common.code")} required>
            <Input className="font-mono uppercase" maxLength={30} disabled={editing !== "new"} value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
          </Field>
          <Field label={t("common.name")} required>
            <Input maxLength={120} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </Field>
        </div>
        <Field label={t("common.description")}>
          <Input maxLength={500} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        </Field>
        <Field label={t("types.defaultFrequency")}>
          <Input type="number" min={1} max={3650} className="font-mono" value={form.default_frequency_days} onChange={(e) => setForm({ ...form, default_frequency_days: e.target.value })} />
        </Field>
      </Modal>
    </>
  );
}
