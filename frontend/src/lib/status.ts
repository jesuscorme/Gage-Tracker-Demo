import type { ControlStatus, GageStatus } from "./types";

export const GAGE_STATUSES: GageStatus[] = [
  "CALIBRATED",
  "DUE_SOON",
  "OVERDUE",
  "OUT_OF_SERVICE",
  "IN_CALIBRATION",
  "INACTIVE",
];

/** CSS custom-property name holding each status colour (defined in globals.css). */
export const STATUS_TONE: Record<GageStatus, string> = {
  CALIBRATED: "ok",
  DUE_SOON: "warn",
  OVERDUE: "bad",
  OUT_OF_SERVICE: "block",
  IN_CALIBRATION: "info",
  INACTIVE: "mute",
};

export interface TransitionOption {
  target: ControlStatus;
  permission: string;
  labelKey: "transition.OUT_OF_SERVICE" | "transition.IN_CALIBRATION" | "transition.ACTIVE" | "transition.REACTIVATE" | "transition.INACTIVE";
  danger?: boolean;
}

// Mirrors backend app/modules/gages/status.py TRANSITIONS. The backend re-checks every one.
const RESTRICT = "gages:restrict";
const RELEASE = "gages:release";
const RETIRE = "gages:retire";

export function transitionsFrom(current: ControlStatus): TransitionOption[] {
  switch (current) {
    case "ACTIVE":
      return [
        { target: "OUT_OF_SERVICE", permission: RESTRICT, labelKey: "transition.OUT_OF_SERVICE" },
        { target: "IN_CALIBRATION", permission: RESTRICT, labelKey: "transition.IN_CALIBRATION" },
        { target: "INACTIVE", permission: RETIRE, labelKey: "transition.INACTIVE", danger: true },
      ];
    case "OUT_OF_SERVICE":
      return [
        { target: "ACTIVE", permission: RELEASE, labelKey: "transition.ACTIVE" },
        { target: "IN_CALIBRATION", permission: RESTRICT, labelKey: "transition.IN_CALIBRATION" },
        { target: "INACTIVE", permission: RETIRE, labelKey: "transition.INACTIVE", danger: true },
      ];
    case "IN_CALIBRATION":
      return [
        { target: "ACTIVE", permission: RELEASE, labelKey: "transition.ACTIVE" },
        { target: "OUT_OF_SERVICE", permission: RESTRICT, labelKey: "transition.OUT_OF_SERVICE" },
        { target: "INACTIVE", permission: RETIRE, labelKey: "transition.INACTIVE", danger: true },
      ];
    case "INACTIVE":
      return [{ target: "ACTIVE", permission: RELEASE, labelKey: "transition.REACTIVATE" }];
  }
}

// ---------------------------------------------------------------- module status tones

type ToneName = "ok" | "warn" | "bad" | "block" | "info" | "mute";

export const CAL_STATUS_TONE: Record<string, ToneName> = {
  PLANNED: "mute", REQUESTED: "info", SCHEDULED: "info", IN_PROGRESS: "warn", PENDING_REVIEW: "warn",
  PENDING_APPROVAL: "warn", APPROVED: "ok", RELEASED: "ok", CANCELLED: "mute",
};
export const CAL_RESULT_TONE: Record<string, ToneName> = { PASS: "ok", PASS_AFTER_ADJUSTMENT: "warn", FAIL: "bad" };
export const STD_STATUS_TONE: Record<string, ToneName> = {
  VALID: "ok", DUE_SOON: "warn", EXPIRED: "bad", NO_CERTIFICATE: "bad", RESTRICTED: "block", INACTIVE: "mute",
};
export const AUTH_STATE_TONE: Record<string, ToneName> = {
  CURRENT: "ok", EXPIRING: "warn", EXPIRED: "bad", REVOKED: "mute", PENDING: "info",
};
export const MATRIX_TONE: Record<string, ToneName> = {
  CURRENT: "ok", EXPIRING: "warn", EXPIRED: "bad", FAILED: "block", NONE: "mute",
};
export const REQ_STATUS_TONE: Record<string, ToneName> = {
  SUBMITTED: "warn", APPROVED: "info", REJECTED: "mute", IN_PROGRESS: "info", COMPLETED: "ok", CANCELLED: "mute",
};
export const WO_STATUS_TONE: Record<string, ToneName> = {
  PENDING: "warn", SCHEDULED: "info", IN_PROGRESS: "info", COMPLETED: "ok", CANCELLED: "mute",
};
export const PRIORITY_TONE: Record<string, ToneName> = { LOW: "mute", NORMAL: "info", HIGH: "warn", URGENT: "bad" };

export const ACTIVITY_TYPES = ["EXTERNAL_CALIBRATION", "INTERNAL_CALIBRATION", "ROUTINE_VERIFICATION"] as const;
export const STANDARD_CATEGORIES = [
  "GAUGE_BLOCK", "REFERENCE_STANDARD", "MASTER_PART", "SETTING_MASTER", "REFERENCE_INSTRUMENT", "TEMPERATURE",
  "PRESSURE", "OTHER",
] as const;
export const AUTH_ACTIVITIES = [
  "INTERNAL_CALIBRATION", "ROUTINE_VERIFICATION", "TECHNICAL_REVIEW", "APPROVAL", "LAB_SERVICE",
  "DIMENSIONAL_INSPECTION", "MSA_EVALUATION",
] as const;
export const PROFILE_TYPES = [
  "METROLOGY_TECHNICIAN", "LAB_TECHNICIAN", "INTERNAL_CALIBRATOR", "VERIFIER", "MSA_EVALUATOR",
  "TECHNICAL_REVIEWER", "APPROVER",
] as const;
