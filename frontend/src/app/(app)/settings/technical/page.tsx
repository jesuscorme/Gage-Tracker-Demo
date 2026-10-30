"use client";

import { useEffect, useState } from "react";
import {
  Alert, Button, Card, Check, ErrorState, Field, Input, Loading, PageHeader, Select, ToneBadge, useAction,
} from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import type { MessageKey } from "@/lib/messages";
import { ACTIVITY_TYPES } from "@/lib/status";
import type { LabService, Person, Plant } from "@/lib/types";

type Req = { enabled: boolean; require_certificate: boolean; require_standard: boolean; require_as_found: boolean;
  require_environment: boolean; source: string };
const REQ_KEYS = ["enabled", "require_certificate", "require_standard", "require_as_found", "require_environment"] as const;

export default function TechnicalSettingsPage() {
  const { t } = useI18n();
  const { can } = useAuth();
  return (
    <>
      <PageHeader eyebrow={t("nav.section.admin")} title={t("nav.settings")} />
      <div className="space-y-4">
        <CalibrationSettings editable={can("calibration:settings")} />
        {can("lab:read") && <LabServices editable={can("lab:manage")} />}
        {can("lab:read") && <LabCapacity editable={can("lab:manage")} />}
      </div>
    </>
  );
}

function CalibrationSettings({ editable }: { editable: boolean }) {
  const { t } = useI18n();
  const plants = useResource(() => api.get<Plant[]>("/plants"));
  const [plant, setPlant] = useState("");
  const cfg = useResource(() => api.get<Record<string, Req>>("/calibration-settings", { plant_id: plant }), [plant]);
  const { busy, error, run } = useAction();
  if (cfg.error) return <ErrorState error={cfg.error} onRetry={cfg.reload} />;
  return (
    <Card flush title={t("cal.settings")} actions={
      <Select className="h-8 max-w-[240px]" value={plant} onChange={(e) => setPlant(e.target.value)} aria-label={t("cal.settings.scope")}>
        <option value="">{t("cal.settings.org")}</option>
        {plants.data?.map((p) => <option key={p.id} value={p.id}>{p.code} — {p.name}</option>)}
      </Select>}>
      {error && <div className="px-4 pt-3"><Alert>{error}</Alert></div>}
      {!cfg.data ? <div className="px-4"><Loading /></div> : (
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead><tr><th>{t("cal.type")}</th>{REQ_KEYS.map((k) => <th key={k}>{t(`cal.req.${k}`)}</th>)}<th>{t("cal.settings.scope")}</th></tr></thead>
            <tbody>
              {ACTIVITY_TYPES.map((type) => {
                const row = cfg.data![type];
                return (
                  <tr key={type}>
                    <td className="font-medium">{t(`cal.type.${type}`)}</td>
                    {REQ_KEYS.map((k) => (
                      <td key={k}>
                        <input type="checkbox" aria-label={t(`cal.req.${k}`)} disabled={!editable || busy !== null} checked={row[k]}
                          onChange={(e) => run(type, () => api.put("/calibration-settings", {
                            plant_id: plant || null, activity_type: type,
                            ...Object.fromEntries(REQ_KEYS.map((x) => [x, x === k ? e.target.checked : row[x]])),
                          }), cfg.reload)} />
                      </td>
                    ))}
                    <td><ToneBadge tone={row.source === "default" ? "mute" : "info"}>{row.source}</ToneBadge></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function LabServices({ editable }: { editable: boolean }) {
  const { t } = useI18n();
  const list = useResource(() => api.get<LabService[]>("/lab/services", { include_inactive: true }));
  const empty = { code: "", name: "", standard_hours: "2", required_activity: "LAB_SERVICE", requires_inspection: true };
  const [f, setF] = useState(empty);
  const { busy, error, run } = useAction();
  return (
    <Card flush title={t("lab.services")}>
      {error && <div className="px-4 pt-3"><Alert>{error}</Alert></div>}
      {list.data?.length ? (
        <table className="data-table">
          <thead><tr><th>{t("common.code")}</th><th>{t("common.name")}</th><th>{t("lab.services.hours")}</th><th>{t("lab.services.activity")}</th>
            <th>{t("lab.services.inspection")}</th><th>{t("common.status")}</th><th /></tr></thead>
          <tbody>
            {list.data.map((s) => (
              <tr key={s.id} className={s.is_active ? "" : "text-ink-3"}>
                <td className="font-mono font-semibold">{s.code}</td><td>{s.name}</td><td className="tabular">{s.standard_hours}</td>
                <td>{t(`comp.act.${s.required_activity}` as MessageKey)}</td><td>{s.requires_inspection ? t("common.yes") : t("common.no")}</td>
                <td>{s.is_active ? t("common.active") : t("common.inactive")}</td>
                <td>{editable && <Button variant="ghost" className="h-7 px-2" onClick={() => run(s.id, () => api.patch(`/lab/services/${s.id}`, { is_active: !s.is_active }), list.reload)}>
                  {s.is_active ? t("users.deactivate") : t("users.activate")}</Button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <p className="px-4 py-4 text-[13px] text-ink-3">{t("comp.empty")}</p>}
      {editable && (
        <div className="grid items-end gap-2 border-t border-line bg-line-2/40 px-4 py-3 sm:grid-cols-[110px_1fr_90px_190px_auto_auto]">
          <Input placeholder={t("common.code")} className="font-mono uppercase" value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} />
          <Input placeholder={t("common.name")} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
          <Input type="number" min={0.25} step={0.25} aria-label={t("lab.services.hours")} value={f.standard_hours} onChange={(e) => setF({ ...f, standard_hours: e.target.value })} />
          <Select value={f.required_activity} onChange={(e) => setF({ ...f, required_activity: e.target.value })} aria-label={t("lab.services.activity")}>
            <option value="LAB_SERVICE">{t("comp.act.LAB_SERVICE")}</option><option value="DIMENSIONAL_INSPECTION">{t("comp.act.DIMENSIONAL_INSPECTION")}</option>
          </Select>
          <Check label={t("lab.services.inspection")} checked={f.requires_inspection} onChange={(v) => setF({ ...f, requires_inspection: v })} />
          <Button variant="primary" disabled={!f.code || f.name.length < 2} loading={busy === "new"}
            onClick={() => run("new", () => api.post("/lab/services", f), () => { setF(empty); list.reload(); })}>+ {t("lab.services.new")}</Button>
        </div>
      )}
    </Card>
  );
}

function LabCapacity({ editable }: { editable: boolean }) {
  const { t, fmtDate } = useI18n();
  const s = useResource(() => api.get<{ hours_per_technician_day: number; working_days: number[] }>("/lab/settings"));
  const absences = useResource(() => api.get<{ id: string; user_name: string; start_date: string; end_date: string; reason: string | null }[]>("/lab/absences"));
  const people = useResource(() => (editable ? api.get<Person[]>("/competency/people") : Promise.resolve([])));
  const [hours, setHours] = useState("8");
  const [days, setDays] = useState<number[]>([1, 2, 3, 4, 5]);
  const [abs, setAbs] = useState({ user_id: "", start_date: "", end_date: "", reason: "" });
  const { busy, error, run } = useAction();
  useEffect(() => { if (s.data) { setHours(String(s.data.hours_per_technician_day)); setDays(s.data.working_days); } }, [s.data]);
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title={t("lab.capacity")}>
        {error && <div className="mb-3"><Alert>{error}</Alert></div>}
        <Field label={t("lab.capacity.hours")}><Input type="number" min={1} max={24} step={0.5} disabled={!editable} value={hours} onChange={(e) => setHours(e.target.value)} /></Field>
        <fieldset className="mt-3">
          <legend className="mb-1 text-[12px] font-medium text-ink-2">{t("lab.capacity.days")}</legend>
          <div className="flex flex-wrap gap-3">
            {[1, 2, 3, 4, 5, 6, 7].map((d) => (
              <Check key={d} disabled={!editable} label={t(`lab.weekday.${d}` as MessageKey)} checked={days.includes(d)}
                onChange={(v) => setDays(v ? [...days, d].sort() : days.filter((x) => x !== d))} />
            ))}
          </div>
        </fieldset>
        {editable && <Button className="mt-3" variant="primary" loading={busy === "cap"} disabled={!days.length}
          onClick={() => run("cap", () => api.put("/lab/settings", { hours_per_technician_day: hours, working_days: days }), s.reload)}>{t("common.save")}</Button>}
      </Card>
      <Card flush title={t("lab.absences")}>
        {absences.data?.length ? (
          <ul className="divide-y divide-line-2">
            {absences.data.map((a) => (
              <li key={a.id} className="flex justify-between px-4 py-2 text-[13px]">
                <span>{a.user_name}</span><span className="tabular text-ink-2">{fmtDate(a.start_date)} – {fmtDate(a.end_date)}</span>
              </li>
            ))}
          </ul>
        ) : <p className="px-4 py-4 text-[13px] text-ink-3">{t("comp.empty")}</p>}
        {editable && (
          <div className="grid gap-2 border-t border-line bg-line-2/40 px-4 py-3 sm:grid-cols-2">
            <Select value={abs.user_id} onChange={(e) => setAbs({ ...abs, user_id: e.target.value })} aria-label={t("common.user")}>
              <option value="" />{people.data?.map((p) => <option key={p.user_id} value={p.user_id}>{p.full_name}</option>)}
            </Select>
            <Input placeholder={t("common.reason")} value={abs.reason} onChange={(e) => setAbs({ ...abs, reason: e.target.value })} />
            <Input type="date" aria-label={t("common.from")} className="font-mono" value={abs.start_date} onChange={(e) => setAbs({ ...abs, start_date: e.target.value })} />
            <Input type="date" aria-label={t("common.to")} className="font-mono" value={abs.end_date} onChange={(e) => setAbs({ ...abs, end_date: e.target.value })} />
            <Button variant="primary" className="sm:col-span-2" disabled={!abs.user_id || !abs.start_date || !abs.end_date} loading={busy === "abs"}
              onClick={() => run("abs", () => api.post("/lab/absences", { ...abs, reason: abs.reason || null }),
                () => { setAbs({ user_id: "", start_date: "", end_date: "", reason: "" }); absences.reload(); })}>+ {t("lab.absences.new")}</Button>
          </div>
        )}
      </Card>
    </div>
  );
}
