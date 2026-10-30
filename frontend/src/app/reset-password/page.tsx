"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { AuthFrame } from "@/components/auth-frame";
import { Alert, Button, Field, Input, errorText } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

function ResetForm() {
  const { t } = useI18n();
  const token = useSearchParams().get("token") ?? "";
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [state, setState] = useState<{ ok?: boolean; error?: string }>({});
  const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (pw !== confirm) return setState({ error: t("acc.mismatch") });
    setBusy(true);
    try {
      await api.post("/auth/reset-password", { token, new_password: pw });
      setState({ ok: true });
    } catch (err) {
      setState({ error: err instanceof ApiError && err.code === "invalid_reset_token" ? t("acc.resetInvalid") : errorText(t, err) });
    } finally {
      setBusy(false);
    }
  }
  return (
    <AuthFrame title={t("acc.resetTitle")} subtitle={t("acc.policy")}>
      {state.ok ? (
        <Alert tone="ok">{t("acc.resetDone")} <Link className="font-semibold text-accent" href="/login">{t("auth.login.submit")}</Link></Alert>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          {state.error && <Alert>{state.error}</Alert>}
          {!token && <Alert>{t("acc.resetInvalid")}</Alert>}
          <Field label={t("acc.new")}><Input type="password" autoComplete="new-password" required value={pw} onChange={(e) => setPw(e.target.value)} /></Field>
          <Field label={t("acc.confirm")}><Input type="password" autoComplete="new-password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} /></Field>
          <Button type="submit" variant="primary" className="w-full" loading={busy} disabled={!token}>{t("acc.resetTitle")}</Button>
        </form>
      )}
    </AuthFrame>
  );
}

export default function ResetPasswordPage() {
  return <Suspense><ResetForm /></Suspense>;
}
