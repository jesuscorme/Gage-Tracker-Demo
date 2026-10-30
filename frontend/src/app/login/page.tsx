"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthFrame } from "@/components/auth-frame";
import { Alert, Button, Field, Input, errorText } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export default function LoginPage() {
  const { t } = useI18n();
  const { login, me, ready } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (ready && me) router.replace("/dashboard");
  }, [ready, me, router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? t("auth.invalid") : errorText(t, err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthFrame title={t("auth.login.title")} subtitle={t("auth.login.subtitle")}>
      <form onSubmit={submit} className="space-y-4">
        {error && <Alert>{error}</Alert>}
        <Field label={t("auth.email")}>
          <Input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label={t("auth.password")}>
          <Input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        <Button type="submit" variant="primary" className="w-full" loading={busy}>
          {t("auth.login.submit")}
        </Button>
      </form>
      <p className="mt-6 text-[13px] text-ink-3">
        {t("auth.login.noAccount")}{" "}
        <Link href="/register" className="font-medium text-accent hover:underline">
          {t("auth.login.register")}
        </Link>
      </p>
    </AuthFrame>
  );
}
