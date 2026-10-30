"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { localToday, useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import type { Department, Gage, GageType, OrgUser, Plant } from "@/lib/types";
import { CustomFieldInputs, type Values, useFieldDefs } from "./custom-fields";
import { Alert, Button, Card, Field, Input, Select, Textarea, errorText } from "./ui";

type FormState = Record<
  | "gage_code" | "description" | "gage_type_id" | "plant_id" | "department_id" | "manufacturer" | "model"
  | "serial_number" | "range_min" | "range_max" | "unit" | "resolution" | "accuracy" | "criticality"
  | "location" | "responsible_user_id" | "calibration_frequency_days" | "last_calibration_date" | "notes"
  | "acquisition_date" | "in_service_date",
  string
>;

const NUMERIC = new Set(["range_min", "range_max", "resolution"]);
// Changed through their own controlled operations once the gage exists.
const CREATE_ONLY = new Set(["gage_code", "plant_id", "department_id", "location", "responsible_user_id", "last_calibration_date"]);
const INTEGER = new Set(["calibration_frequency_days"]);

function fromGage(g?: Gage): FormState {
  return {
    gage_code: g?.gage_code ?? "",
    description: g?.description ?? "",
    gage_type_id: g?.gage_type.id ?? "",
    plant_id: g?.plant.id ?? "",
    department_id: g?.department?.id ?? "",
    manufacturer: g?.manufacturer ?? "",
    model: g?.model ?? "",
    serial_number: g?.serial_number ?? "",
    range_min: g?.range_min ?? "",
    range_max: g?.range_max ?? "",
    unit: g?.unit ?? "",
    resolution: g?.resolution ?? "",
    accuracy: g?.accuracy ?? "",
    criticality: g?.criticality ?? "",
    location: g?.location ?? "",
    responsible_user_id: g?.responsible?.id ?? "",
    calibration_frequency_days: g ? String(g.calibration_frequency_days) : "",
    last_calibration_date: g?.last_calibration_date ?? "",
    notes: g?.notes ?? "",
    acquisition_date: g?.acquisition_date ?? "",
    in_service_date: g?.in_service_date ?? "",
  };
}

function toPayload(k: string, v: string): unknown {
  const s = v.trim();
  if (s === "") return null;
  if (INTEGER.has(k)) return Number(s);
  if (NUMERIC.has(k)) return s; // decimals travel as strings to keep precision
  return s;
}

export function GageForm({ gage }: { gage?: Gage }) {
  const { t } = useI18n();
  const { can } = useAuth();
  const router = useRouter();
  const editing = !!gage;
  const initial = useMemo(() => fromGage(gage), [gage]);
  const [form, setForm] = useState<FormState>(initial);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [custom, setCustom] = useState<Values>({});
  const fieldDefs = useFieldDefs("gage");

  const plants = useResource(() => api.get<Plant[]>("/plants"));
  const types = useResource(() => api.get<GageType[]>("/gage-types"));
  const departments = useResource(() => api.get<Department[]>("/departments"));
  const users = useResource(() => (can("users:read") ? api.get<OrgUser[]>("/users") : Promise.resolve([])));

  const canMoveDueDate = !editing || can("gages:release");
  const set = (k: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value, ...(k === "plant_id" ? { department_id: "" } : {}) }));

  const selectedType = types.data?.find((x) => x.id === form.gage_type_id);
  const deptOptions = (departments.data ?? []).filter((d) => d.plant_id === form.plant_id && d.is_active);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      let saved: Gage;
      if (editing) {
        const changes: Record<string, unknown> = {};
        for (const k of Object.keys(form) as (keyof FormState)[]) {
          if (CREATE_ONLY.has(k)) continue;
          if (form[k] !== initial[k]) changes[k] = toPayload(k, form[k]);
        }
        saved = Object.keys(changes).length ? await api.patch<Gage>(`/gages/${gage.id}`, changes) : gage;
      } else {
        const body: Record<string, unknown> = {};
        for (const [k, v] of Object.entries(form)) {
          const p = toPayload(k, v);
          if (p !== null) body[k] = p;
        }
        body.custom_fields = custom;
        saved = await api.post<Gage>("/gages", body);
      }
      router.push(`/gages/${saved.id}`);
    } catch (err) {
      setError(errorText(t, err));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      {error && <Alert>{error}</Alert>}

      <Card title={t("gage.section.identification")}>
        <div className="grid gap-4 md:grid-cols-[200px_1fr_260px]">
          <Field label={t("gage.field.code")} required>
            <Input
              required
              disabled={editing}
              maxLength={50}
              pattern="[A-Za-z0-9][A-Za-z0-9._/\-]*"
              className="font-mono uppercase"
              value={form.gage_code}
              onChange={set("gage_code")}
            />
          </Field>
          <Field label={t("gage.field.description")} required>
            <Input required minLength={2} maxLength={300} value={form.description} onChange={set("description")} />
          </Field>
          <Field label={t("gage.field.type")} required>
            <Select required value={form.gage_type_id} onChange={set("gage_type_id")}>
              <option value="" />
              {types.data?.map((x) => (
                <option key={x.id} value={x.id}>{x.name} ({x.code})</option>
              ))}
              {gage && !types.data?.some((x) => x.id === gage.gage_type.id) && (
                <option value={gage.gage_type.id}>{gage.gage_type.name}</option>
              )}
            </Select>
          </Field>
          <Field label={t("gage.field.manufacturer")}>
            <Input maxLength={120} value={form.manufacturer} onChange={set("manufacturer")} />
          </Field>
          <Field label={t("gage.field.model")}>
            <Input maxLength={120} value={form.model} onChange={set("model")} />
          </Field>
          <Field label={t("gage.field.serial")}>
            <Input maxLength={120} className="font-mono" value={form.serial_number} onChange={set("serial_number")} />
          </Field>
        </div>
      </Card>

      <Card title={t("gage.section.specs")}>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
          <Field label={t("gage.field.rangeMin")}>
            <Input inputMode="decimal" className="font-mono" value={form.range_min} onChange={set("range_min")} />
          </Field>
          <Field label={t("gage.field.rangeMax")}>
            <Input inputMode="decimal" className="font-mono" value={form.range_max} onChange={set("range_max")} />
          </Field>
          <Field label={t("gage.field.unit")}>
            <Input maxLength={20} placeholder="mm" value={form.unit} onChange={set("unit")} />
          </Field>
          <Field label={t("gage.field.resolution")}>
            <Input inputMode="decimal" className="font-mono" placeholder="0.01" value={form.resolution} onChange={set("resolution")} />
          </Field>
          <Field label={t("gage.field.accuracy")}>
            <Input maxLength={120} placeholder="±0.02 mm" value={form.accuracy} onChange={set("accuracy")} />
          </Field>
          <Field label={t("gage.field.criticality")}>
            <Select value={form.criticality} onChange={set("criticality")}>
              <option value="">—</option>
              {(["LOW", "MEDIUM", "HIGH"] as const).map((c) => (
                <option key={c} value={c}>{t(`gage.criticality.${c}`)}</option>
              ))}
            </Select>
          </Field>
        </div>
      </Card>

      <Card title={t("gage.section.assignment")} actions={editing && <span className="text-[12px] text-ink-3">🔒 {t("gage.transfer")}</span>}>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label={t("gage.field.plant")} required>
            <Select required disabled={editing} value={form.plant_id} onChange={set("plant_id")}>
              <option value="" />
              {plants.data?.filter((p) => p.is_active || p.id === form.plant_id).map((p) => (
                <option key={p.id} value={p.id}>{p.code} — {p.name}</option>
              ))}
            </Select>
          </Field>
          <Field label={t("gage.field.department")}>
            <Select value={form.department_id} onChange={set("department_id")} disabled={editing || !form.plant_id}>
              <option value="">—</option>
              {deptOptions.map((d) => (
                <option key={d.id} value={d.id}>{d.code} — {d.name}</option>
              ))}
            </Select>
          </Field>
          <Field label={t("gage.field.location")}>
            <Input maxLength={200} disabled={editing} value={form.location} onChange={set("location")} />
          </Field>
          <Field label={t("gage.field.responsible")}>
            <Select disabled={editing} value={form.responsible_user_id} onChange={set("responsible_user_id")}>
              <option value="">—</option>
              {users.data?.filter((u) => u.is_active).map((u) => (
                <option key={u.id} value={u.id}>{u.full_name}</option>
              ))}
              {gage?.responsible && !users.data?.some((u) => u.id === gage.responsible!.id) && (
                <option value={gage.responsible.id}>{gage.responsible.full_name}</option>
              )}
            </Select>
          </Field>
        </div>
      </Card>

      <Card title={t("gage.section.calibration")}>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field
            label={t("gage.field.frequency")}
            hint={!editing && selectedType?.default_frequency_days ? `${t("gage.field.frequencyHint")} (${selectedType.default_frequency_days})` : undefined}
            required={editing || !selectedType?.default_frequency_days}
          >
            <Input
              type="number"
              min={1}
              max={3650}
              className="font-mono"
              disabled={!canMoveDueDate}
              required={editing || (!!selectedType && !selectedType.default_frequency_days)}
              value={form.calibration_frequency_days}
              onChange={set("calibration_frequency_days")}
            />
          </Field>
          <Field label={t("gage.field.lastCalibration")} hint={!editing ? t("gage.initialCalibrationHint") : undefined}>
            <Input
              type="date"
              className="font-mono"
              disabled={editing}
              max={localToday()}
              value={form.last_calibration_date}
              onChange={set("last_calibration_date")}
            />
          </Field>
          <Field label={t("gage.field.acquisition")}>
            <Input type="date" className="font-mono" max={localToday()} value={form.acquisition_date} onChange={set("acquisition_date")} />
          </Field>
          <Field label={t("gage.field.inService")}>
            <Input type="date" className="font-mono" max={localToday()} value={form.in_service_date} onChange={set("in_service_date")} />
          </Field>
        </div>
        {editing && !canMoveDueDate && <p className="mt-3 text-[12px] text-ink-3">🔒 {t("gage.restrictedFields")}</p>}
        <Field label={t("gage.field.notes")} className="mt-4">
          <Textarea maxLength={4000} value={form.notes} onChange={set("notes")} />
        </Field>
      </Card>

      {!gage && !!fieldDefs.data?.length && (
        <Card title={t("cf.title")}><CustomFieldInputs defs={fieldDefs.data} values={custom} onChange={setCustom} /></Card>
      )}

      <div className="flex justify-end gap-2">
        <Button type="button" onClick={() => router.back()}>{t("common.cancel")}</Button>
        <Button type="submit" variant="primary" loading={busy}>{editing ? t("common.save") : t("common.create")}</Button>
      </div>
    </form>
  );
}
