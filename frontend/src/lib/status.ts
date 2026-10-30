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
