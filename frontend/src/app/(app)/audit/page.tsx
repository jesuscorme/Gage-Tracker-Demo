"use client";

import Link from "next/link";
import { useState } from "react";
import { Card, EmptyState, ErrorState, Loading, PageHeader, Pagination, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import type { AuditEvent } from "@/lib/types";

const PAGE = 50;
const ENTITY_TYPES = ["gage", "gage_type", "user", "organization", "plant", "department"];

export default function AuditPage() {
  const { t, fmtDateTime } = useI18n();
  const [entity, setEntity] = useState("");
  const [page, setPage] = useState(1);
  const events = useResource(
    () => api.get<{ items: AuditEvent[]; total: number }>("/audit-events", { entity_type: entity, limit: PAGE, offset: (page - 1) * PAGE }),
    [entity, page],
  );

  return (
    <>
      <PageHeader eyebrow={t("nav.section.admin")} title={t("audit.title")} />
      <Card flush>
        <div className="border-b border-line p-3">
          <Select
            className="max-w-[240px]"
            value={entity}
            onChange={(e) => {
              setEntity(e.target.value);
              setPage(1);
            }}
            aria-label={t("audit.filterEntity")}
          >
            <option value="">{t("audit.filterEntity")}: {t("common.all")}</option>
            {ENTITY_TYPES.map((e) => <option key={e} value={e}>{e}</option>)}
          </Select>
        </div>
        {events.error ? (
          <div className="px-4"><ErrorState error={events.error} onRetry={events.reload} /></div>
        ) : !events.data ? (
          <div className="px-4"><Loading /></div>
        ) : events.data.items.length === 0 ? (
          <EmptyState>{t("audit.empty")}</EmptyState>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t("common.date")}</th>
                    <th>{t("common.user")}</th>
                    <th>{t("audit.action")}</th>
                    <th>{t("audit.entity")}</th>
                    <th className="hidden lg:table-cell">{t("audit.changes")}</th>
                  </tr>
                </thead>
                <tbody>
                  {events.data.items.map((e) => (
                    <tr key={e.id}>
                      <td className="tabular whitespace-nowrap text-[12px]">{fmtDateTime(e.created_at)}</td>
                      <td>{e.actor_name ?? "—"}</td>
                      <td className="font-mono text-[12px] font-semibold">{e.action}</td>
                      <td className="font-mono text-[12px]">
                        {e.entity_type === "gage" && e.entity_id ? (
                          <Link className="text-accent hover:underline" href={`/gages/${e.entity_id}`}>gage/{e.entity_id.slice(0, 8)}</Link>
                        ) : (
                          `${e.entity_type}${e.entity_id ? `/${e.entity_id.slice(0, 8)}` : ""}`
                        )}
                      </td>
                      <td className="hidden max-w-[420px] lg:table-cell">
                        <code className="line-clamp-2 break-all text-[11px] text-ink-2">
                          {e.reason ? `“${e.reason}” ` : ""}
                          {e.changes ? JSON.stringify(e.changes) : ""}
                        </code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} pageSize={PAGE} total={events.data.total} onPage={setPage} />
          </>
        )}
      </Card>
    </>
  );
}
