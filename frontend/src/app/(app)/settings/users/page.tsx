"use client";

import { useState } from "react";
import { Alert, Button, Card, ErrorState, Field, Input, Loading, Modal, PageHeader, Select, cx, errorText } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import type { OrgUser, Plant, Role } from "@/lib/types";

interface Draft {
  email: string;
  full_name: string;
  password: string;
  role_code: string;
  plant_ids: string[];
}
const EMPTY: Draft = { email: "", full_name: "", password: "", role_code: "metrology_technician", plant_ids: [] };

export default function UsersPage() {
  const { t, fmtDateTime } = useI18n();
  const { can, me } = useAuth();
  const manage = can("users:manage");
  const users = useResource(() => api.get<OrgUser[]>("/users"));
  const roles = useResource(() => api.get<Role[]>("/roles"));
  const plants = useResource(() => api.get<Plant[]>("/plants"));
  const [editing, setEditing] = useState<OrgUser | "new" | null>(null);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function open(u: OrgUser | "new") {
    setError(null);
    setEditing(u);
    setDraft(u === "new" ? EMPTY : { ...EMPTY, email: u.email, full_name: u.full_name, role_code: u.role_code, plant_ids: u.plants.map((p) => p.id) });
  }

  async function save() {
    setBusy(true);
    setError(null);
    try {
      if (editing === "new") await api.post("/users", draft);
      else if (editing) await api.patch(`/users/${editing.id}`, { role_code: draft.role_code, plant_ids: draft.plant_ids });
      setEditing(null);
      users.reload();
    } catch (err) {
      setError(errorText(t, err));
    } finally {
      setBusy(false);
    }
  }

  async function toggle(u: OrgUser) {
    setError(null);
    try {
      await api.patch(`/users/${u.id}`, { is_active: !u.is_active });
      users.reload();
    } catch (err) {
      setError(errorText(t, err));
    }
  }

  if (users.error) return <ErrorState error={users.error} onRetry={users.reload} />;
  if (!users.data) return <Loading />;

  return (
    <>
      <PageHeader
        eyebrow={t("nav.section.admin")}
        title={t("users.title")}
        actions={manage && <Button variant="primary" onClick={() => open("new")}>+ {t("users.new")}</Button>}
      />
      {error && !editing && <div className="mb-3"><Alert>{error}</Alert></div>}
      <Card flush>
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("common.name")}</th>
                <th>{t("users.role")}</th>
                <th>{t("users.plants")}</th>
                <th className="hidden md:table-cell">{t("users.lastLogin")}</th>
                <th>{t("gages.col.status")}</th>
                {manage && <th className="text-right">{t("common.actions")}</th>}
              </tr>
            </thead>
            <tbody>
              {users.data.map((u) => (
                <tr key={u.id} className={cx(!u.is_active && "text-ink-3")}>
                  <td>
                    <div className="font-medium">{u.full_name}</div>
                    <div className="text-[12px] text-ink-3">{u.email}</div>
                  </td>
                  <td>{u.role_name}</td>
                  <td className="font-mono text-[12px]">{u.plants.length ? u.plants.map((p) => p.code).join(", ") : t("users.allPlants")}</td>
                  <td className="hidden tabular text-[12px] text-ink-2 md:table-cell">{fmtDateTime(u.last_login_at)}</td>
                  <td>{u.is_active ? t("common.active") : t("common.inactive")}</td>
                  {manage && (
                    <td className="text-right">
                      <div className="inline-flex gap-1">
                        <Button variant="ghost" className="h-7 px-2" onClick={() => open(u)}>{t("common.edit")}</Button>
                        {u.id !== me?.id && (
                          <Button variant="ghost" className="h-7 px-2" onClick={() => toggle(u)}>
                            {u.is_active ? t("users.deactivate") : t("users.activate")}
                          </Button>
                        )}
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Modal
        open={!!editing}
        onClose={() => setEditing(null)}
        title={editing === "new" ? t("users.new") : `${t("common.edit")} · ${draft.full_name}`}
        footer={
          <>
            <Button onClick={() => setEditing(null)}>{t("common.cancel")}</Button>
            <Button variant="primary" loading={busy} onClick={save}>{t("common.save")}</Button>
          </>
        }
      >
        {error && <Alert>{error}</Alert>}
        {editing === "new" && (
          <>
            <Field label={t("auth.register.fullName")} required>
              <Input value={draft.full_name} onChange={(e) => setDraft({ ...draft, full_name: e.target.value })} />
            </Field>
            <Field label={t("auth.email")} required>
              <Input type="email" value={draft.email} onChange={(e) => setDraft({ ...draft, email: e.target.value })} />
            </Field>
            <Field label={t("users.initialPassword")} hint={t("auth.register.passwordHint")} required>
              <Input type="password" autoComplete="new-password" value={draft.password} onChange={(e) => setDraft({ ...draft, password: e.target.value })} />
            </Field>
          </>
        )}
        <Field label={t("users.role")} required>
          <Select value={draft.role_code} onChange={(e) => setDraft({ ...draft, role_code: e.target.value })}>
            {roles.data?.map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}
          </Select>
        </Field>
        <fieldset>
          <legend className="mb-1 text-[12px] font-medium text-ink-2">{t("users.plants")}</legend>
          <div className="flex flex-wrap gap-x-4 gap-y-1.5">
            {plants.data?.map((p) => (
              <label key={p.id} className="flex items-center gap-1.5 text-[13px]">
                <input
                  type="checkbox"
                  checked={draft.plant_ids.includes(p.id)}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      plant_ids: e.target.checked ? [...draft.plant_ids, p.id] : draft.plant_ids.filter((x) => x !== p.id),
                    })
                  }
                />
                <span className="font-mono">{p.code}</span> {p.name}
              </label>
            ))}
          </div>
          <p className="mt-1 text-[12px] text-ink-3">{t("users.plantsHint")}</p>
        </fieldset>
      </Modal>
    </>
  );
}
