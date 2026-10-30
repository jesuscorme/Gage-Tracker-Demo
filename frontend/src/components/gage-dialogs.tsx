"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { localToday, useResource } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { ACTIVITY_TYPES } from "@/lib/status";
import type { ActivityDetail, Department, Gage, OrgUser, Plant } from "@/lib/types";
import { Alert, Button, Field, Input, Modal, Select, Textarea, errorText } from "./ui";

/** Reassign responsible and/or transfer the gage (records a movement with reason). */
export function TransferDialog({ gage, open, onClose, onDone }: {
  gage: Gage;
  open: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const { t } = useI18n();
  const { can } = useAuth();
  const plants = useResource(() => (open ? api.get<Plant[]>("/plants") : Promise.resolve([])), [open]);
  const depts = useResource(() => (open ? api.get<Department[]>("/departments") : Promise.resolve([])), [open]);
  const users = useResource(() => (open && can("users:read") ? api.get<OrgUser[]>("/users") : Promise.resolve([])), [open]);
  const [f, setF] = useState({ plant_id: "", department_id: "", location: "", responsible_user_id: "", reason: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) setF({ plant_id: gage.plant.id, department_id: gage.department?.id ?? "", location: gage.location ?? "",
      responsible_user_id: gage.responsible?.id ?? "", reason: "" });
  }, [open, gage]);

  async function save() {
    setBusy(true);
    setError(null);
    const body: Record<string, unknown> = { reason: f.reason.trim() };
    if (f.plant_id !== gage.plant.id) body.plant_id = f.plant_id;
    if (f.department_id !== (gage.department?.id ?? "")) body.department_id = f.department_id || null;
    if (f.location !== (gage.location ?? "")) body.location = f.location || null;
    if (f.responsible_user_id !== (gage.responsible?.id ?? "")) body.responsible_user_id = f.responsible_user_id || null;
    try {
      await api.post(`/gages/${gage.id}/transfer`, body);
      onDone();
    } catch (err) {
      setError(errorText(t, err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={`${t("gage.transfer.title")} · ${gage.gage_code}`}
      footer={<><Button onClick={onClose}>{t("common.cancel")}</Button>
        <Button variant="primary" loading={busy} disabled={f.reason.trim().length < 3} onClick={save}>{t("common.save")}</Button></>}>
      {error && <Alert>{error}</Alert>}
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("gage.field.plant")}>
          <Select value={f.plant_id} onChange={(e) => setF({ ...f, plant_id: e.target.value, department_id: "" })}>
            {plants.data?.map((p) => <option key={p.id} value={p.id}>{p.code} — {p.name}</option>)}
          </Select>
        </Field>
        <Field label={t("gage.field.department")}>
          <Select value={f.department_id} onChange={(e) => setF({ ...f, department_id: e.target.value })}>
            <option value="">—</option>
            {depts.data?.filter((d) => d.plant_id === f.plant_id && d.is_active).map((d) => <option key={d.id} value={d.id}>{d.code} — {d.name}</option>)}
          </Select>
        </Field>
        <Field label={t("gage.field.location")}>
          <Input maxLength={200} value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })} />
        </Field>
        <Field label={t("gage.field.responsible")}>
          <Select value={f.responsible_user_id} onChange={(e) => setF({ ...f, responsible_user_id: e.target.value })}>
            <option value="">—</option>
            {users.data?.filter((u) => u.is_active).map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
          </Select>
        </Field>
      </div>
      <Field label={t("common.reasonRequired")} required>
        <Textarea maxLength={1000} value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} />
      </Field>
    </Modal>
  );
}

/** Plan a calibration / verification activity for a gage. */
export function PlanCalibrationDialog({ gages, gageId, open, onClose }: {
  gages?: Gage[];
  gageId?: string;
  open: boolean;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const router = useRouter();
  const [f, setF] = useState({ gage_id: gageId ?? "", activity_type: "INTERNAL_CALIBRATION", planned_date: "", provider_name: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open) setF((x) => ({ ...x, gage_id: gageId ?? x.gage_id, planned_date: localToday() }));
  }, [open, gageId]);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const a = await api.post<ActivityDetail>("/calibrations", {
        gage_id: f.gage_id, activity_type: f.activity_type, planned_date: f.planned_date,
        provider_name: f.provider_name || null,
      });
      router.push(`/calibrations/${a.id}`);
    } catch (err) {
      setError(errorText(t, err));
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={t("cal.new")}
      footer={<><Button onClick={onClose}>{t("common.cancel")}</Button>
        <Button variant="primary" loading={busy} disabled={!f.gage_id || !f.planned_date} onClick={save}>{t("common.create")}</Button></>}>
      {error && <Alert>{error}</Alert>}
      {gages && (
        <Field label="Gage ID" required>
          <Select value={f.gage_id} onChange={(e) => setF({ ...f, gage_id: e.target.value })}>
            <option value="" />
            {gages.map((g) => <option key={g.id} value={g.id}>{g.gage_code} — {g.description}</option>)}
          </Select>
        </Field>
      )}
      <Field label={t("cal.type")} required>
        <Select value={f.activity_type} onChange={(e) => setF({ ...f, activity_type: e.target.value })}>
          {ACTIVITY_TYPES.map((a) => <option key={a} value={a}>{t(`cal.type.${a}`)}</option>)}
        </Select>
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("cal.planned")} required>
          <Input type="date" className="font-mono" value={f.planned_date} onChange={(e) => setF({ ...f, planned_date: e.target.value })} />
        </Field>
        {f.activity_type === "EXTERNAL_CALIBRATION" && (
          <Field label={t("cal.provider")}>
            <Input maxLength={200} value={f.provider_name} onChange={(e) => setF({ ...f, provider_name: e.target.value })} />
          </Field>
        )}
      </div>
    </Modal>
  );
}
