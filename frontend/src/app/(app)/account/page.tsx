"use client";

import { useState } from "react";
import { Alert, Button, Card, Field, Input, PageHeader, Select, useAction } from "@/components/ui";
import { api, session } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export default function AccountPage() {
  const { t } = useI18n();
  const { me, logout } = useAuth();
  const [pw, setPw] = useState({ current: "", next: "", confirm: "" });
  const [lang, setLang] = useState(me?.preferred_language ?? "es");
  const [msg, setMsg] = useState<string | null>(null);
  const { busy, error, run, setError } = useAction();
  return (
    <>
      <PageHeader title={t("acc.title")} eyebrow={me?.email} />
      <div className="grid max-w-3xl gap-4">
        {msg && <Alert tone="ok">{msg}</Alert>}
        {error && <Alert>{error}</Alert>}
        <Card title={t("acc.changePassword")}>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label={t("acc.current")}><Input type="password" autoComplete="current-password" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} /></Field>
            <Field label={t("acc.new")} hint={t("acc.policy")}><Input type="password" autoComplete="new-password" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} /></Field>
            <Field label={t("acc.confirm")}><Input type="password" autoComplete="new-password" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} /></Field>
          </div>
          <Button className="mt-3" variant="primary" disabled={!!busy || !pw.current || !pw.next} onClick={() => {
            if (pw.next !== pw.confirm) { setError(t("acc.mismatch")); return; }
            run("pw", async () => {
              const r = await api.post<{ access_token: string }>("/auth/change-password", { current_password: pw.current, new_password: pw.next });
              session.setToken(r.access_token);
            }, () => { setPw({ current: "", next: "", confirm: "" }); setMsg(t("acc.changed")); });
          }}>{t("acc.changePassword")}</Button>
        </Card>
        <Card title={t("acc.language")}>
          <div className="flex items-end gap-2">
            <Select className="w-40" value={lang} onChange={(e) => setLang(e.target.value as "es" | "en")}><option value="es">Español</option><option value="en">English</option></Select>
            <Button disabled={!!busy} onClick={() => run("lang", () => api.patch("/auth/me", { preferred_language: lang }), () => setMsg(t("acc.saved")))}>{t("common.save")}</Button>
          </div>
        </Card>
        <Card title={t("acc.logoutAll")}>
          <p className="mb-3 text-[13px] text-ink-3">{t("acc.logoutAllHelp")}</p>
          <Button variant="danger" disabled={!!busy} onClick={() => run("all", () => api.post("/auth/logout-all"), logout)}>{t("acc.logoutAll")}</Button>
        </Card>
      </div>
    </>
  );
}
