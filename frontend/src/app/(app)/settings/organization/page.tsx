"use client";

import { useEffect, useState } from "react";
import { Alert, Button, Card, ErrorState, Field, Input, Loading, PageHeader, Select, cx, errorText } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import type { Department, Organization, Plant } from "@/lib/types";

export default function OrganizationPage() {
  const { t } = useI18n();
  const { can } = useAuth();
  const org = useResource(() => api.get<Organization>("/organization"));
  const plants = useResource(() => api.get<Plant[]>("/plants"));
  const departments = useResource(() => api.get<Department[]>("/departments"));

  if (org.error) return <ErrorState error={org.error} onRetry={org.reload} />;
  if (!org.data) return <Loading />;

  return (
    <>
      <PageHeader eyebrow={t("nav.section.admin")} title={t("org.title")}>
        <p className="mt-1 font-mono text-[12px] text-ink-3">{org.data.slug}</p>
      </PageHeader>
      <div className="grid gap-4 xl:grid-cols-[380px_1fr]">
        <OrgSettings org={org.data} editable={can("organization:manage")} onSaved={org.reload} />
        <div className="space-y-4">
          <Plants plants={plants.data ?? []} editable={can("plants:manage")} onChange={plants.reload} />
          <Departments
            plants={plants.data ?? []}
            departments={departments.data ?? []}
            editable={can("plants:manage")}
            onChange={departments.reload}
          />
        </div>
      </div>
    </>
  );
}

function OrgSettings({ org, editable, onSaved }: { org: Organization; editable: boolean; onSaved: () => void }) {
  const { t } = useI18n();
  const [form, setForm] = useState({ name: org.name, due_soon_days: String(org.due_soon_days), timezone: org.timezone });
  const [msg, setMsg] = useState<{ tone: "ok" | "bad"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => setForm({ name: org.name, due_soon_days: String(org.due_soon_days), timezone: org.timezone }), [org]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      await api.patch("/organization", { name: form.name, due_soon_days: Number(form.due_soon_days), timezone: form.timezone });
      setMsg({ tone: "ok", text: t("org.saved") });
      onSaved();
    } catch (err) {
      setMsg({ tone: "bad", text: errorText(t, err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title={t("org.settings")}>
      <form onSubmit={save} className="space-y-4">
        {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}
        <Field label={t("auth.register.orgName")}>
          <Input disabled={!editable} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </Field>
        <Field label={t("org.dueSoonDays")} hint={t("org.dueSoonHint")}>
          <Input type="number" min={0} max={365} className="font-mono" disabled={!editable} value={form.due_soon_days} onChange={(e) => setForm({ ...form, due_soon_days: e.target.value })} />
        </Field>
        <Field label={t("org.timezone")}>
          <Input className="font-mono" disabled={!editable} value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} />
        </Field>
        {editable && <Button type="submit" variant="primary" loading={busy}>{t("common.save")}</Button>}
      </form>
    </Card>
  );
}

function InlineCreate({ fields, onSubmit, label }: {
  fields: { key: string; label: string; mono?: boolean; options?: { value: string; label: string }[] }[];
  onSubmit: (values: Record<string, string>) => Promise<void>;
  label: string;
}) {
  const { t } = useI18n();
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit(values);
      setValues({});
    } catch (err) {
      setError(errorText(t, err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-2 border-t border-line bg-line-2/40 px-4 py-3">
      {error && <Alert>{error}</Alert>}
      <div className="flex flex-wrap items-end gap-2">
        {fields.map((f) => (
          <Field key={f.key} label={f.label} className={f.mono ? "w-28" : "min-w-[160px] flex-1"}>
            {f.options ? (
              <Select required value={values[f.key] ?? ""} onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}>
                <option value="" />
                {f.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </Select>
            ) : (
              <Input required className={cx(f.mono && "font-mono uppercase")} value={values[f.key] ?? ""} onChange={(e) => setValues({ ...values, [f.key]: e.target.value })} />
            )}
          </Field>
        ))}
        <Button type="submit" variant="primary" loading={busy}>+ {label}</Button>
      </div>
    </form>
  );
}

function Plants({ plants, editable, onChange }: { plants: Plant[]; editable: boolean; onChange: () => void }) {
  const { t } = useI18n();
  return (
    <Card flush title={t("org.plants")}>
      <table className="data-table">
        <thead><tr><th>{t("common.code")}</th><th>{t("common.name")}</th><th>{t("gages.col.status")}</th>{editable && <th />}</tr></thead>
        <tbody>
          {plants.map((p) => (
            <tr key={p.id} className={cx(!p.is_active && "text-ink-3")}>
              <td className="font-mono font-semibold">{p.code}</td>
              <td>{p.name}</td>
              <td>{p.is_active ? t("common.active") : t("common.inactive")}</td>
              {editable && (
                <td className="text-right">
                  <Button variant="ghost" className="h-7 px-2" onClick={() => api.patch(`/plants/${p.id}`, { is_active: !p.is_active }).then(onChange, (e) => window.alert(errorText(t, e)))}>
                    {p.is_active ? t("users.deactivate") : t("users.activate")}
                  </Button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {editable && (
        <InlineCreate
          label={t("org.newPlant")}
          fields={[{ key: "code", label: t("common.code"), mono: true }, { key: "name", label: t("common.name") }]}
          onSubmit={async (v) => {
            await api.post("/plants", v);
            onChange();
          }}
        />
      )}
    </Card>
  );
}

function Departments({ plants, departments, editable, onChange }: {
  plants: Plant[];
  departments: Department[];
  editable: boolean;
  onChange: () => void;
}) {
  const { t } = useI18n();
  const plantCode = (id: string) => plants.find((p) => p.id === id)?.code ?? "—";
  return (
    <Card flush title={t("org.departments")}>
      {departments.length > 0 && (
        <table className="data-table">
          <thead><tr><th>{t("gage.field.plant")}</th><th>{t("common.code")}</th><th>{t("common.name")}</th><th>{t("gages.col.status")}</th>{editable && <th />}</tr></thead>
          <tbody>
            {departments.map((d) => (
              <tr key={d.id} className={cx(!d.is_active && "text-ink-3")}>
                <td className="font-mono text-ink-2">{plantCode(d.plant_id)}</td>
                <td className="font-mono font-semibold">{d.code}</td>
                <td>{d.name}</td>
                <td>{d.is_active ? t("common.active") : t("common.inactive")}</td>
                {editable && (
                  <td className="text-right">
                    <Button variant="ghost" className="h-7 px-2" onClick={() => api.patch(`/departments/${d.id}`, { is_active: !d.is_active }).then(onChange, (e) => window.alert(errorText(t, e)))}>
                      {d.is_active ? t("users.deactivate") : t("users.activate")}
                    </Button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {editable && (
        <InlineCreate
          label={t("org.newDepartment")}
          fields={[
            { key: "plant_id", label: t("gage.field.plant"), options: plants.filter((p) => p.is_active).map((p) => ({ value: p.id, label: `${p.code} — ${p.name}` })) },
            { key: "code", label: t("common.code"), mono: true },
            { key: "name", label: t("common.name") },
          ]}
          onSubmit={async (v) => {
            await api.post("/departments", v);
            onChange();
          }}
        />
      )}
    </Card>
  );
}
