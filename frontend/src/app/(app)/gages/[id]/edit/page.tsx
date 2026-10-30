"use client";

import { useParams } from "next/navigation";
import { GageForm } from "@/components/gage-form";
import { Alert, ErrorState, Loading, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import type { Gage } from "@/lib/types";

export default function EditGagePage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useI18n();
  const { can } = useAuth();
  const gage = useResource(() => api.get<Gage>(`/gages/${id}`), [id]);

  if (!can("gages:update")) return <Alert>{t("common.forbidden")}</Alert>;
  if (gage.error) return <ErrorState error={gage.error} onRetry={gage.reload} />;
  if (!gage.data) return <Loading />;

  return (
    <>
      <PageHeader eyebrow={t("gage.edit.title")} title={<span className="font-mono">{gage.data.gage_code}</span>} />
      <GageForm key={gage.data.updated_at} gage={gage.data} />
    </>
  );
}
