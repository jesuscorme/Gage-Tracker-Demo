"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { TransitionOption } from "@/lib/status";
import type { Gage } from "@/lib/types";
import { Alert, Button, Field, Input, Modal, Textarea, errorText } from "./ui";

export function TransitionDialog({
  gage,
  option,
  onClose,
  onDone,
}: {
  gage: Gage;
  option: TransitionOption | null;
  onClose: () => void;
  onDone: (g: Gage) => void;
}) {
  const { t } = useI18n();
  const [reason, setReason] = useState("");
  const [calDate, setCalDate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const releasingFromCalibration = option?.target === "ACTIVE" && gage.control_status === "IN_CALIBRATION";

  function close() {
    setReason("");
    setCalDate("");
    setError(null);
    onClose();
  }

  async function confirm() {
    if (!option) return;
    setBusy(true);
    setError(null);
    try {
      const g = await api.post<Gage>(`/gages/${gage.id}/transitions`, {
        target: option.target,
        reason: reason.trim(),
        ...(releasingFromCalibration && calDate ? { calibration_date: calDate } : {}),
      });
      setReason("");
      setCalDate("");
      onDone(g);
    } catch (err) {
      setError(errorText(t, err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={!!option}
      onClose={close}
      title={`${t("transition.title")} · ${gage.gage_code}${option ? ` → ${t(option.labelKey)}` : ""}`}
      footer={
        <>
          <Button onClick={close}>{t("common.cancel")}</Button>
          <Button
            variant={option?.danger ? "danger" : "primary"}
            loading={busy}
            disabled={reason.trim().length < 3}
            onClick={confirm}
          >
            {t("transition.confirm")}
          </Button>
        </>
      }
    >
      {error && <Alert>{error}</Alert>}
      <Field label={t("common.reason")} hint={t("transition.reasonHint")} required>
        <Textarea autoFocus maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} />
      </Field>
      {releasingFromCalibration && (
        <Field label={t("transition.calibrationDate")} hint={t("transition.calibrationDateHint")}>
          <Input type="date" className="font-mono" value={calDate} onChange={(e) => setCalDate(e.target.value)} />
        </Field>
      )}
      {option?.target === "ACTIVE" && <p className="text-[12px] text-ink-3">{t("transition.releaseNote")}</p>}
    </Modal>
  );
}
