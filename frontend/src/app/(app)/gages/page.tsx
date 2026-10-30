"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { DueCell } from "@/components/gage-bits";
import { Icon } from "@/components/icons";
import {
  Button, Card, EmptyState, ErrorState, Input, LinkButton, Loading, PageHeader, Pagination, Select, StatusBadge,
} from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { GAGE_STATUSES } from "@/lib/status";
import type { Gage, GageType, Page, Plant } from "@/lib/types";

const PAGE_SIZE = 25;

export default function GagesPage() {
  return (
    <Suspense fallback={<Loading />}>
      <GageList />
    </Suspense>
  );
}

function GageList() {
  const { t } = useI18n();
  const { can } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const q = params.get("q") ?? "";
  const status = params.get("status") ?? "";
  const plant = params.get("plant_id") ?? "";
  const type = params.get("gage_type_id") ?? "";
  const available = params.get("available") ?? "";
  const includeInactive = params.get("include_inactive") === "true";
  const sort = params.get("sort") ?? "gage_code";
  const page = Number(params.get("page") ?? 1);

  const [search, setSearch] = useState(q);
  useEffect(() => setSearch(q), [q]);

  function update(changes: Record<string, string | null>) {
    const next = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(changes)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    if (!("page" in changes)) next.delete("page");
    router.replace(`${pathname}?${next.toString()}`);
  }

  const plants = useResource(() => api.get<Plant[]>("/plants"));
  const types = useResource(() => api.get<GageType[]>("/gage-types", { include_inactive: true }));
  const list = useResource(
    () =>
      api.get<Page<Gage>>("/gages", {
        q, status, plant_id: plant, gage_type_id: type, available,
        include_inactive: includeInactive, sort, page, page_size: PAGE_SIZE,
      }),
    [q, status, plant, type, available, includeInactive, sort, page],
  );

  const hasFilters = q || status || plant || type || available || includeInactive;
  const sortBy = (key: string) => update({ sort: sort === key ? `-${key}` : key });
  const arrow = (key: string) => (sort === key ? " ▲" : sort === `-${key}` ? " ▼" : "");

  return (
    <>
      <PageHeader
        title={t("gages.title")}
        actions={
          <>
            <Button onClick={() => api.download("/gages/export", { format: "xlsx", q, status, plant_id: plant, gage_type_id: type, available, include_inactive: includeInactive })}>
              <Icon name="download" size={14} /> {t("common.export")}
            </Button>
            {can("gages:import") && <LinkButton href="/gages/import"><Icon name="upload" size={14} /> {t("common.import")}</LinkButton>}
            {can("gages:create") && <LinkButton href="/gages/new" variant="primary">+ {t("gages.new")}</LinkButton>}
          </>
        }
      />

      <Card flush>
        <form
          className="grid gap-2 border-b border-line p-3 sm:grid-cols-2 lg:grid-cols-[minmax(220px,2fr)_repeat(4,minmax(130px,1fr))_auto]"
          onSubmit={(e) => {
            e.preventDefault();
            update({ q: search.trim() || null });
          }}
        >
          <Input
            type="search"
            placeholder={t("gages.searchPlaceholder")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onBlur={() => search.trim() !== q && update({ q: search.trim() || null })}
            aria-label={t("common.search")}
          />
          <Select value={status} onChange={(e) => update({ status: e.target.value || null })} aria-label={t("gages.filter.status")}>
            <option value="">{t("gages.filter.status")}: {t("common.all")}</option>
            {GAGE_STATUSES.map((s) => (
              <option key={s} value={s}>{t(`status.${s}`)}</option>
            ))}
          </Select>
          <Select value={plant} onChange={(e) => update({ plant_id: e.target.value || null })} aria-label={t("gages.filter.plant")}>
            <option value="">{t("gages.filter.plant")}: {t("common.all")}</option>
            {plants.data?.map((p) => (
              <option key={p.id} value={p.id}>{p.code} — {p.name}</option>
            ))}
          </Select>
          <Select value={type} onChange={(e) => update({ gage_type_id: e.target.value || null })} aria-label={t("gages.filter.type")}>
            <option value="">{t("gages.filter.type")}: {t("common.all")}</option>
            {types.data?.map((g) => (
              <option key={g.id} value={g.id}>{g.name}</option>
            ))}
          </Select>
          <Select value={available} onChange={(e) => update({ available: e.target.value || null })} aria-label={t("gages.filter.availability")}>
            <option value="">{t("gages.filter.availability")}: {t("common.all")}</option>
            <option value="true">{t("status.available")}</option>
            <option value="false">{t("status.notAvailable")}</option>
          </Select>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 whitespace-nowrap text-[12px] text-ink-2">
              <input
                type="checkbox"
                checked={includeInactive}
                onChange={(e) => update({ include_inactive: e.target.checked ? "true" : null })}
              />
              {t("gages.filter.includeInactive")}
            </label>
            {hasFilters && (
              <Button type="button" variant="ghost" className="h-8 px-2" onClick={() => router.replace(pathname)}>
                {t("common.clear")}
              </Button>
            )}
          </div>
        </form>

        {list.error ? (
          <div className="px-4"><ErrorState error={list.error} onRetry={list.reload} /></div>
        ) : !list.data ? (
          <div className="px-4"><Loading /></div>
        ) : list.data.items.length === 0 ? (
          <EmptyState>{t("gages.empty")}</EmptyState>
        ) : (
          <>
            <div className={`overflow-x-auto ${list.loading ? "opacity-60" : ""}`}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th><button onClick={() => sortBy("gage_code")}>{t("gages.col.id")}{arrow("gage_code")}</button></th>
                    <th><button onClick={() => sortBy("description")}>{t("gages.col.description")}{arrow("description")}</button></th>
                    <th className="hidden lg:table-cell">{t("gages.col.type")}</th>
                    <th className="hidden md:table-cell">{t("gages.col.plant")}</th>
                    <th className="hidden xl:table-cell">{t("gages.col.location")}</th>
                    <th><button onClick={() => sortBy("next_due_date")}>{t("gages.col.due")}{arrow("next_due_date")}</button></th>
                    <th>{t("gages.col.status")}</th>
                  </tr>
                </thead>
                <tbody>
                  {list.data.items.map((g) => (
                    <tr key={g.id} className={g.control_status === "INACTIVE" ? "text-ink-3" : ""}>
                      <td>
                        <Link href={`/gages/${g.id}`} className="font-mono text-[13px] font-semibold text-accent hover:underline">
                          {g.gage_code}
                        </Link>
                        {g.serial_number && <div className="font-mono text-[11px] text-ink-3">S/N {g.serial_number}</div>}
                      </td>
                      <td className="max-w-[300px]">
                        <div className="truncate">{g.description}</div>
                        {(g.manufacturer || g.model) && (
                          <div className="truncate text-[11px] text-ink-3">{[g.manufacturer, g.model].filter(Boolean).join(" · ")}</div>
                        )}
                      </td>
                      <td className="hidden text-ink-2 lg:table-cell">{g.gage_type.name}</td>
                      <td className="hidden font-mono text-[12px] text-ink-2 md:table-cell">
                        {g.plant.code}
                        {g.department && ` / ${g.department.code}`}
                      </td>
                      <td className="hidden max-w-[180px] truncate text-ink-2 xl:table-cell">{g.location ?? "—"}</td>
                      <td><DueCell gage={g} /></td>
                      <td><StatusBadge status={g.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              page={page}
              pageSize={PAGE_SIZE}
              total={list.data.total}
              onPage={(p) => update({ page: String(p) })}
            />
          </>
        )}
      </Card>
    </>
  );
}
