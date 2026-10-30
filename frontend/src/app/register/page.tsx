"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthFrame } from "@/components/auth-frame";
import { Alert, Button, Field, Input, errorText } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

function browserTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

export default function RegisterPage() {
  const { t, lang } = useI18n();
  const { register, me, ready } = useAuth();
  const router = useRouter();
  const [form, setForm] = useState({
    organization_name: "",
    plant_code: "",
    plant_name: "",
    timezone: "UTC",
    full_name: "",
    email: "",
    password: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => setForm((f) => ({ ...f, timezone: browserTimeZone() })), []);
  useEffect(() => {
    if (ready && me) router.replace("/dashboard");
  }, [ready, me, router]);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await register({ ...form, preferred_language: lang });
    } catch (err) {
      setError(errorText(t, err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthFrame title={t("auth.register.title")} subtitle={t("auth.register.subtitle")}>
      <form onSubmit={submit} className="space-y-4">
        {error && <Alert>{error}</Alert>}
        <Field label={t("auth.register.orgName")} required>
          <Input required minLength={2} value={form.organization_name} onChange={set("organization_name")} />
        </Field>
        <div className="grid grid-cols-[120px_1fr] gap-3">
          <Field label={t("auth.register.plantCode")} required>
            <Input required maxLength={30} className="font-mono uppercase" value={form.plant_code} onChange={set("plant_code")} />
          </Field>
          <Field label={t("auth.register.plantName")} required>
            <Input required minLength={2} value={form.plant_name} onChange={set("plant_name")} />
          </Field>
        </div>
        <Field label={t("auth.register.timezone")}>
          <Input value={form.timezone} onChange={set("timezone")} className="font-mono" />
        </Field>
        <hr className="border-line" />
        <Field label={t("auth.register.fullName")} required>
          <Input required minLength={2} autoComplete="name" value={form.full_name} onChange={set("full_name")} />
        </Field>
        <Field label={t("auth.email")} required>
          <Input type="email" required autoComplete="username" value={form.email} onChange={set("email")} />
        </Field>
        <Field label={t("auth.password")} hint={t("auth.register.passwordHint")} required>
          <Input type="password" required minLength={10} autoComplete="new-password" value={form.password} onChange={set("password")} />
        </Field>
        <Button type="submit" variant="primary" className="w-full" loading={busy}>
          {t("auth.register.submit")}
        </Button>
      </form>
      <p className="mt-6 text-[13px] text-ink-3">
        {t("auth.register.haveAccount")}{" "}
        <Link href="/login" className="font-medium text-accent hover:underline">
          {t("auth.login.submit")}
        </Link>
      </p>
    </AuthFrame>
  );
}
