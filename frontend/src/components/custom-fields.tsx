"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import type { CustomFieldDef } from "@/lib/types-b3";
import { IssueList } from "./workflow";
import { Alert, Button, Card, Check, Field, Input, Select, useAction } from "./ui";

export type Values = Record<string, unknown>;

function visible(d: CustomFieldDef, values: Values) {
  if (!d.visible_when) return true;
  const cur = values[d.visible_when.field];
  const eq = d.visible_when.equals;
  return Array.isArray(eq) ? eq.includes(cur) : cur === eq;
}

/** Inputs for the organization's custom fields of a record type (controlled). */
export function CustomFieldInputs({ defs, values, onChange }: {
  defs: CustomFieldDef[]; values: Values; onChange: (v: Values) => void;
}) {
  const set = (k: string, v: unknown) => onChange({ ...values, [k]: v });
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {defs.filter((d) => visible(d, values)).map((d) => {
        const v = values[d.key];
        const label = d.label;
        if (d.field_type === "BOOLEAN") {
          return <div key={d.key} className="pt-5"><Check label={label} checked={v === true} onChange={(c) => set(d.key, c)} /></div>;
        }
        return (
          <Field key={d.key} label={label} required={d.required} hint={d.help_text ?? undefined}>
            {d.field_type === "LIST" ? (
              <Select value={(v as string) ?? ""} onChange={(e) => set(d.key, e.target.value || null)}>
                <option value="">—</option>
                {d.options.map((o) => <option key={o} value={o}>{o}</option>)}
              </Select>
            ) : d.field_type === "MULTISELECT" ? (
              <Select multiple value={(v as string[]) ?? []}
                onChange={(e) => set(d.key, Array.from(e.target.selectedOptions).map((o) => o.value))}>
                {d.options.map((o) => <option key={o} value={o}>{o}</option>)}
              </Select>
            ) : (
              <Input type={d.field_type === "NUMBER" ? "number" : d.field_type === "DATE" ? "date" : "text"}
                value={v === null || v === undefined ? "" : String(v)} maxLength={d.max_length ?? undefined}
                onChange={(e) => set(d.key, e.target.value === "" ? null
                  : d.field_type === "NUMBER" ? Number(e.target.value) : e.target.value)} />
            )}
          </Field>
        );
      })}
    </div>
  );
}

export function useFieldDefs(entity: string) {
  return useResource(() => api.get<CustomFieldDef[]>(`/custom-fields/${entity}`), [entity]);
}

/** Card showing and editing the custom field values of one record. */
export function CustomFieldsCard({ entity, id, canEdit }: { entity: string; id: string; canEdit: boolean }) {
  const { t } = useI18n();
  const defs = useFieldDefs(entity);
  const vals = useResource(() => api.get<Values>(`/custom-fields/${entity}/${id}`), [entity, id]);
  const [draft, setDraft] = useState<Values>({});
  const [saved, setSaved] = useState(false);
  const [lastError, setLastError] = useState<unknown>(null);
  const { busy, error, run } = useAction();
  useEffect(() => setDraft(vals.data ?? {}), [vals.data]);
  if (!defs.data?.length) return null;
  return (
    <Card title={t("cf.title")}>
      {error && <Alert>{error}<IssueList error={lastError} /></Alert>}
      {saved && <Alert tone="ok">{t("cf.saved")}</Alert>}
      {canEdit ? (
        <>
          <CustomFieldInputs defs={defs.data} values={draft} onChange={(v) => { setDraft(v); setSaved(false); }} />
          <div className="mt-3">
            <Button variant="primary" disabled={!!busy} onClick={() => run("save", async () => {
              setLastError(null);
              try {
                await api.put(`/custom-fields/${entity}/${id}`, { values: draft });
              } catch (e) {
                setLastError(e);
                throw e;
              }
            }, () => { setSaved(true); vals.reload(); })}>{t("common.save")}</Button>
          </div>
        </>
      ) : (
        <dl className="grid gap-2 text-[13px] sm:grid-cols-2">
          {defs.data.map((d) => (
            <div key={d.key}><dt className="text-[11px] text-ink-3">{d.label}</dt>
              <dd>{vals.data?.[d.key] === undefined ? "—" : String(vals.data[d.key])}</dd></div>
          ))}
        </dl>
      )}
    </Card>
  );
}
