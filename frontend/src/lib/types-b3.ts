// Types of the third increment: MSA, OOT, configuration, integrations and compliance.

export type MsaMethod =
  | "GRR_CROSSED_AR" | "GRR_CROSSED_ANOVA" | "GRR_NESTED_ANOVA" | "ATTRIBUTE_AGREEMENT"
  | "BIAS" | "LINEARITY" | "STABILITY" | "TYPE1";
export const MSA_METHODS: MsaMethod[] = [
  "GRR_CROSSED_ANOVA", "GRR_CROSSED_AR", "GRR_NESTED_ANOVA", "ATTRIBUTE_AGREEMENT", "BIAS", "LINEARITY", "STABILITY", "TYPE1",
];
export type MsaFamily = "VARIABLE_GRR" | "ATTRIBUTE" | "BIAS" | "LINEARITY" | "STABILITY" | "TYPE1";
export const FAMILY: Record<MsaMethod, MsaFamily> = {
  GRR_CROSSED_AR: "VARIABLE_GRR", GRR_CROSSED_ANOVA: "VARIABLE_GRR", GRR_NESTED_ANOVA: "VARIABLE_GRR",
  ATTRIBUTE_AGREEMENT: "ATTRIBUTE", BIAS: "BIAS", LINEARITY: "LINEARITY", STABILITY: "STABILITY", TYPE1: "TYPE1",
};
export const OBS_FIELDS: Record<MsaFamily, string[]> = {
  VARIABLE_GRR: ["operator", "part", "trial", "value"],
  ATTRIBUTE: ["operator", "part", "trial", "category"],
  BIAS: ["trial", "value"],
  TYPE1: ["trial", "value"],
  LINEARITY: ["part", "reference", "trial", "value"],
  STABILITY: ["subgroup", "trial", "value", "measured_at"],
};
export type Decision = "ACCEPTABLE" | "CONDITIONAL" | "NOT_ACCEPTABLE" | "INCONCLUSIVE" | "NO_CRITERIA";

export interface MsaStudy {
  id: string; study_code: string; title: string; method: MsaMethod; status: string; workflow_version: number;
  characteristic: string; part_number: string | null; part_revision: string | null; customer: string | null;
  plant_id: string; department_id: string | null; gage_id: string; gage_code: string | null;
  gage_description: string | null; responsible_id: string; start_date: string; end_date: string | null;
  design: Record<string, unknown>; params: Record<string, unknown>; criteria_set_id: string | null;
  notes: string | null; final_decision: Decision | null; final_comment: string | null;
  concluded_by: string | null; concluded_at: string | null; created_at: string; latest_decision: Decision | null;
}

export interface MsaObservation {
  id: string; operator: string | null; part: string | null; trial: number | null; subgroup: number | null;
  value: string | null; category: string | null; reference: string | null; measured_at: string | null;
  source: string; superseded: boolean; supersedes_id: string | null; correction_reason: string | null;
  recorded_at: string;
}

export interface Component { source: string; sd: number; variance: number; study_var: number;
  pct_contribution: number | null; pct_study_var: number | null; pct_tolerance: number | null }
export interface MsaResults {
  method: MsaMethod; algorithm_version: string; engine_version: string; validation_status: string; model: string;
  design: Record<string, unknown>; metrics: Record<string, number | boolean | null>;
  tables: Record<string, any>; charts: Record<string, any>; intermediate: Record<string, unknown>; warnings: string[];
}
export interface Evaluation { metric: string; op: string; value: number | boolean; actual: number | boolean | null;
  status: string; label?: string | null }
export interface MsaRun {
  id: string; study_id: string; run_number: number; method: MsaMethod; algorithm_version: string;
  engine_version: string; validation_status: string; input_hash: string; results: MsaResults;
  criteria_set_id: string | null; criteria_snapshot: { name: string; version: number; source: string; scope: string } | null;
  evaluation: Evaluation[] | null; decision: Decision; gage_snapshot: Record<string, string | null>;
  calculated_by: string; calculated_at: string; guidance: Guidance[]; observations: MsaObservationRow[];
}
export interface MsaObservationRow { operator?: string; part?: string; trial?: number; subgroup?: string; reference?: number; value: number | string }
export interface Guidance { level: "ok" | "warn" | "bad" | "info"; es: string; en: string; ref: { es: string; en: string } }
export interface RunSummary { id: string; run_number: number; algorithm_version: string; engine_version: string;
  validation_status: string; input_hash: string; decision: Decision; calculated_at: string }
export interface CriteriaRule { metric: string; op: string; value: number | boolean; outcome?: string; label?: string }
export interface CriteriaSet {
  id: string; name: string; version: number; method: MsaMethod; scope: string; plant_id: string | null;
  customer: string | null; rules: CriteriaRule[]; source: string; status: string; created_by: string;
  created_at: string; approved_by: string | null; approved_at: string | null; retired_at: string | null;
}
export interface CriteriaTemplate { name: string; methods: MsaMethod[]; source: string; rules: CriteriaRule[] }
export interface MethodInfo { code: MsaMethod; family: MsaFamily; algorithm_version: string; validation: string;
  evidence: string; observation_fields: string[]; metrics: string[] }
export interface MsaReport { id: string; run_id: string; revision: number; attachment_id: string; issued_at: string }
export interface Issue { code: string; message: string; row?: number; field?: string }

export interface WorkflowTransition { code: string; label: string; to: string; action: string; require_comment: boolean;
  approvals_required: number; votes: number; allowed: boolean; reason: string | null }
export interface WorkflowEventRow { event_type: string; transition: string | null; action: string | null;
  from_state: string | null; to_state: string | null; comment: string | null; actor_id: string | null;
  occurred_at: string; data: Record<string, unknown> | null }
export interface WorkflowState { state: string; version: number; states: { code: string; label: string }[];
  capabilities: string[]; transitions: WorkflowTransition[]; history: WorkflowEventRow[] }

export interface OotCase {
  id: string; case_code: string; plant_id: string; gage_id: string; gage_code: string | null;
  gage_description: string | null; gage_control_status: string | null; calibration_id: string | null;
  detection_source: string; detected_on: string; description: string; found_result: string | null;
  tolerance: string | null; max_deviation: string | null;
  as_found: { sequence: number; description: string | null; nominal: string; lower: string; upper: string;
    measured: string; unit: string | null; in_tolerance: boolean; deviation_outside: string }[] | null;
  as_left: OotCase["as_found"]; responsible_id: string; status: string; restriction_applied: boolean;
  gage_prior_control_status: string | null; gage_released_at: string | null; gage_release_reason: string | null;
  last_acceptable_calibration_id: string | null; impact_start: string | null; impact_end: string | null;
  analysis_generated_at: string | null; limitations: string | null; risk_level: string | null;
  risk_assessment: string | null; investigation_scope: string | null; reinspection: string | null;
  containment: string | null; disposition: string | null; corrective_actions: string | null;
  customer_notification_required: boolean | null; customer_notification: string | null;
  customer_notified_on: string | null; closed_at: string | null; created_at: string; close_gaps: string[];
}
export interface OotItem { id: string; item_type: string; source: string; ref_code: string | null; description: string;
  occurred_at: string | null; data: Record<string, unknown> | null; assessment: string; assessment_note: string | null }
export interface OotAction { id: string; action_type: string; description: string; owner_id: string;
  due_date: string | null; status: string; result_note: string | null; completed_at: string | null }
export interface CalHistoryRow { id: string; calibration_code: string; activity_type: string; status: string;
  performed_date: string | null; result: string | null; as_found_in_tolerance: boolean | null;
  as_left_in_tolerance: boolean | null; is_last_acceptable: boolean; is_detection: boolean }

export interface ConfigVersion { id: string; version: number; status: string; definition: Record<string, any>;
  change_summary: string; created_by: string; created_at: string; decided_by: string | null; decided_at: string | null;
  decision_comment: string | null }
export interface ConfigItem { id: string; kind: string; key: string; entity_type: string; active_version: number | null;
  is_retired: boolean; active: ConfigVersion | null; draft: ConfigVersion | null; version_count: number }
export interface ConfigCatalogue {
  kinds: string[]; needs_approval: string[]; field_types: string[]; text_formats: string[]; operators: string[];
  field_entities: Record<string, string[]>;
  workflow_entities: Record<string, { system_states: Record<string, string>; capabilities: string[];
    facts: Record<string, string>; default_definition: Record<string, any> }>;
  approval_entities: string[]; approval_actions: string[]; permissions: string[]; roles: string[]; activities: string[];
}
export interface CustomFieldDef { entity_type: string; key: string; label: string; field_type: string; required: boolean;
  help_text?: string | null; options: string[]; min_value?: number | null; max_value?: number | null;
  max_length?: number | null; text_format?: string; visible_when?: { field: string; equals: unknown } | null;
  order: number; version: number }

export interface ImportJob { id: string; importer: string; target_id: string | null; filename: string; mapping: Record<string, string>;
  status: string; total_rows: number; valid_rows: number; error_count: number;
  errors: { row: number | null; key?: string; field?: string; errors: string[] }[]; preview: Record<string, string | null>[];
  summary: Record<string, number> | null; reprocess_of_id: string | null; created_at: string; committed_at: string | null }
export interface Importer { code: string; label: string; permission: string; target: string | null; allowed: boolean;
  fields: { name: string; required: boolean; aliases: string[] }[] }
export interface ApiClientRow { id: string; name: string; key_prefix: string; created_at: string; expires_at: string | null;
  last_used_at: string | null; revoked_at: string | null; revoked_reason: string | null; api_key?: string }
export interface Webhook { id: string; name: string; url: string; event_types: string[]; is_active: boolean;
  created_at: string; secret?: string }
export interface Delivery { id: string; endpoint_id: string; event_type: string; status: string; attempts: number;
  next_attempt_at: string | null; last_status_code: number | null; last_error: string | null;
  delivered_at: string | null; created_at: string }
export interface Device { id: string; device_code: string; name: string; adapter: string; plant_id: string;
  serial_number: string | null; gage_id: string | null; is_active: boolean }
export interface Reading { id: string; reading_uid: string; value: string; unit: string | null; raw: string;
  gage_status: string | null; captured_at: string }
export interface AdapterInfo { code: string; name: string; status: string; device_kinds: string[]; description: string }

export interface ProcessEvidence { process: string; description: string; evidence: Record<string, number>;
  gaps: Record<string, number>; state: string; clauses: string[] }
export interface ComplianceMatrix { disclaimer: string; generated_at: string; processes: ProcessEvidence[];
  clauses: { standard: string; clause: string; title: string; processes: string[]; state: string }[] }
