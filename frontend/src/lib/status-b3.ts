import type { Tone } from "@/components/ui";
import type { Decision } from "./types-b3";

export const DECISION_TONE: Record<Decision, Tone> = {
  ACCEPTABLE: "ok", CONDITIONAL: "warn", NOT_ACCEPTABLE: "bad", INCONCLUSIVE: "mute", NO_CRITERIA: "mute",
};
export const ASSESSMENT_TONE: Record<string, Tone> = { PENDING: "warn", NO_IMPACT: "ok", IMPACT: "bad", REINSPECT: "block" };
export const COMPLIANCE_TONE: Record<string, Tone> = { EVIDENCE_AVAILABLE: "ok", ATTENTION: "warn", NO_RECORDS: "mute" };
export const IMPORT_TONE: Record<string, Tone> = { VALIDATED: "info", INVALID: "bad", COMMITTED: "ok" };
export const DELIVERY_TONE: Record<string, Tone> = { PENDING: "info", SUCCEEDED: "ok", FAILED: "warn", DEAD: "bad" };
