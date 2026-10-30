"use client";

import { useI18n } from "@/lib/i18n";
import type { Gage } from "@/lib/types";
import { cx } from "./ui";

/** Due date with days remaining/overdue, coloured by urgency. */
export function DueCell({ gage }: { gage: Pick<Gage, "next_due_date" | "days_to_due" | "control_status" | "status"> }) {
  const { t, fmtDate } = useI18n();
  if (!gage.next_due_date) return <span className="text-[12px] font-medium text-bad">{t("gages.noCalibration")}</span>;
  const d = gage.days_to_due ?? 0;
  const muted = gage.control_status === "INACTIVE";
  return (
    <div className="leading-tight">
      <div className="tabular text-[13px]">{fmtDate(gage.next_due_date)}</div>
      {!muted && (
        <div className={cx("tabular text-[11px]", d < 0 ? "font-semibold text-bad" : gage.status === "DUE_SOON" ? "text-warn" : "text-ink-3")}>
          {d < 0 ? t("gages.daysOverdue", { n: -d }) : t("gages.daysLeft", { n: d })}
        </div>
      )}
    </div>
  );
}

export function RangeText({ gage }: { gage: Pick<Gage, "range_min" | "range_max" | "unit"> }) {
  if (gage.range_min == null && gage.range_max == null) return <>—</>;
  return (
    <span className="font-mono tabular">
      {gage.range_min ?? "…"} – {gage.range_max ?? "…"} {gage.unit ?? ""}
    </span>
  );
}
