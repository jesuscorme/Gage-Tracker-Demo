"use client";

import { GageForm } from "@/components/gage-form";
import { Alert, PageHeader } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export default function NewGagePage() {
  const { t } = useI18n();
  const { can } = useAuth();
  return (
    <>
      <PageHeader eyebrow={t("gages.title")} title={t("gage.create.title")} />
      {can("gages:create") ? <GageForm /> : <Alert>{t("common.forbidden")}</Alert>}
    </>
  );
}
