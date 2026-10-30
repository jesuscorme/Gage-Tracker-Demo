"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { DECISION_TONE } from "@/lib/status-b3";
import type { MsaStudy, OotCase } from "@/lib/types-b3";
import { Card, EmptyState, LinkButton, ToneBadge } from "./ui";

/** MSA studies and OOT cases of one gage (gage detail tab). */
export function GageQuality({ gageId }: { gageId: string }) {
  const { t, fmtDate } = useI18n();
  const { can } = useAuth();
  const studies = useResource(() => (can("msa:read") ? api.get<MsaStudy[]>("/msa/studies", { gage_id: gageId }) : Promise.resolve([])), [gageId]);
  const cases = useResource(() => (can("oot:read") ? api.get<OotCase[]>("/oot/cases", { gage_id: gageId }) : Promise.resolve([])), [gageId]);
  return (
    <div className="mt-4 space-y-4">
      <Card title={t("msa.title")} flush actions={can("msa:manage") && <LinkButton href="/msa">+ {t("msa.new")}</LinkButton>}>
        {!studies.data?.length ? <EmptyState>{t("msa.empty")}</EmptyState> : (
          <table className="data-table"><tbody>{studies.data.map((s) => (
            <tr key={s.id}><td><Link className="font-mono text-[12px] text-accent hover:underline" href={`/msa/${s.id}`}>{s.study_code}</Link></td>
              <td className="text-[12px]">{t(`msa.m.${s.method}`)}</td><td className="text-[12px]">{s.characteristic}</td><td>{s.status}</td>
              <td>{s.final_decision && <ToneBadge tone={DECISION_TONE[s.final_decision]}>{t(`msa.dec.${s.final_decision}`)}</ToneBadge>}</td></tr>))}</tbody></table>
        )}
      </Card>
      <Card title={t("oot.title")} flush>
        {!cases.data?.length ? <EmptyState>{t("oot.empty")}</EmptyState> : (
          <table className="data-table"><tbody>{cases.data.map((c) => (
            <tr key={c.id}><td><Link className="font-mono text-[12px] text-accent hover:underline" href={`/oot/${c.id}`}>{c.case_code}</Link></td>
              <td className="tabular">{fmtDate(c.detected_on)}</td><td>{c.status}</td>
              <td>{c.restriction_applied && !c.gage_released_at && <ToneBadge tone="bad">{t("oot.restriction")}</ToneBadge>}</td></tr>))}</tbody></table>
        )}
      </Card>
    </div>
  );
}
