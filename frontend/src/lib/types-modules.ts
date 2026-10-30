import type { Gage, GageStatus, Ref } from "./types";

export interface Attachment {
  id: string;
  entity_type: string;
  entity_id: string;
  category: "PHOTO" | "DOCUMENT" | "CERTIFICATE" | "EVIDENCE" | "REPORT";
  title: string | null;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  is_locked: boolean;
  uploaded_by_name: string | null;
  uploaded_at: string;
  removed_at: string | null;
  removal_reason: string | null;
}

export interface Movement {
  id: string;
  changes: Record<string, [string | null, string | null]>;
  reason: string;
  moved_by_name: string | null;
  moved_at: string;
}

export interface ImportResult {
  dry_run: boolean;
  total_rows: number;
  valid_rows: number;
  created: number;
  errors: { row: number; gage_code: string | null; errors: string[] }[];
}

// ---------------------------------------------------------------- standards

export type StandardStatus = "VALID" | "DUE_SOON" | "EXPIRED" | "NO_CERTIFICATE" | "RESTRICTED" | "INACTIVE";

export interface Standard {
  id: string;
  standard_code: string;
  description: string;
  category: string;
  subtype: string | null;
  plant: Ref;
  manufacturer: string | null;
  model: string | null;
  serial_number: string | null;
  range_min: string | null;
  range_max: string | null;
  unit: string | null;
  resolution: string | null;
  accuracy: string | null;
  location: string | null;
  custodian: { id: string; full_name: string } | null;
  calibration_frequency_days: number;
  last_calibration_date: string | null;
  valid_until: string | null;
  days_to_expiry: number | null;
  current_certificate_id: string | null;
  control_status: "ACTIVE" | "RESTRICTED" | "INACTIVE";
  status: StandardStatus;
  usable: boolean;
  notes: string | null;
}

export interface StandardCertificate {
  id: string;
  certificate_number: string;
  issuer: string;
  accreditation: string | null;
  calibration_date: string;
  issue_date: string;
  valid_until: string;
  uncertainty: string | null;
  traceability: string | null;
  attachment_id: string;
  status: "CURRENT" | "SUPERSEDED";
}

export interface StandardUsage {
  usage_id: string;
  calibration_id: string;
  calibration_code: string;
  activity_type: string;
  activity_status: string;
  gage_code: string;
  used_on: string;
  standard_status: string;
  certificate_id: string | null;
  valid_until: string | null;
  is_exception: boolean;
  exception_reason: string | null;
}

// ---------------------------------------------------------------- competency

export interface Person {
  user_id: string;
  full_name: string;
  email: string;
  has_profile: boolean;
  employee_number: string | null;
  job_title: string | null;
  plant_id: string | null;
  department_id: string | null;
  profile_types: string[];
  is_active: boolean;
  notes: string | null;
  current_authorizations: string[];
}

export interface Competency {
  id: string;
  code: string;
  name: string;
  description: string | null;
  validity_months: number | null;
  is_active: boolean;
}

export interface CompetencyRecord {
  id: string;
  user_id: string;
  competency_id: string;
  record_type: string;
  title: string;
  provider: string | null;
  completed_on: string;
  valid_until: string | null;
  result: string;
  score: string | null;
}

export interface AuthorizationT {
  id: string;
  user_id: string;
  user_name: string | null;
  activity: string;
  gage_type_id: string | null;
  plant_id: string | null;
  valid_from: string;
  valid_until: string | null;
  basis: string | null;
  granted_at: string;
  revoked_at: string | null;
  revoke_reason: string | null;
  state: "CURRENT" | "EXPIRING" | "EXPIRED" | "REVOKED" | "PENDING";
}

export type MatrixCell = "CURRENT" | "EXPIRING" | "EXPIRED" | "FAILED" | "NONE";

export interface Matrix {
  competencies: { id: string; code: string; name: string }[];
  rows: { user_id: string; full_name: string; job_title: string | null; profile_types: string[];
    cells: Record<string, MatrixCell> }[];
}

// ---------------------------------------------------------------- calibration

export type ActivityType = "EXTERNAL_CALIBRATION" | "INTERNAL_CALIBRATION" | "ROUTINE_VERIFICATION";
export type ActivityStatus =
  | "PLANNED" | "REQUESTED" | "SCHEDULED" | "IN_PROGRESS" | "PENDING_REVIEW" | "PENDING_APPROVAL"
  | "APPROVED" | "RELEASED" | "CANCELLED";
export type CalResult = "PASS" | "PASS_AFTER_ADJUSTMENT" | "FAIL";

export interface Activity {
  id: string;
  calibration_code: string;
  activity_type: ActivityType;
  status: ActivityStatus;
  gage_id: string;
  gage_code: string;
  gage_description: string;
  plant_id: string;
  planned_date: string;
  scheduled_date: string | null;
  provider_name: string | null;
  provider_accreditation: string | null;
  technician_id: string | null;
  technician_name: string | null;
  started_at: string | null;
  performed_date: string | null;
  method: string | null;
  environment_temperature: string | null;
  environment_humidity: string | null;
  environment_notes: string | null;
  uncertainty: string | null;
  adjusted: boolean;
  declared_result: CalResult | null;
  observations: string | null;
  result: CalResult | null;
  as_found_in_tolerance: boolean | null;
  as_left_in_tolerance: boolean | null;
  submitted_at: string | null;
  reviewer_name: string | null;
  reviewed_at: string | null;
  review_comments: string | null;
  approver_name: string | null;
  approved_at: string | null;
  released_at: string | null;
  released_by_name: string | null;
  due_date: string | null;
  cancel_reason: string | null;
  created_at: string;
}

export interface CalPoint {
  id: string;
  phase: "AS_FOUND" | "AS_LEFT";
  sequence: number;
  description: string | null;
  nominal: string;
  lower_limit: string;
  upper_limit: string;
  measured: string;
  unit: string | null;
  uncertainty: string | null;
  in_tolerance: boolean;
  superseded: boolean;
  supersedes_id: string | null;
  correction_reason: string | null;
  recorded_at: string;
}

export interface CalCertificate {
  id: string;
  certificate_number: string;
  issuer: string;
  issue_date: string;
  attachment_id: string;
  status: "CURRENT" | "SUPERSEDED";
  superseded_reason: string | null;
  uploaded_at: string;
}

export interface ActivityDetail extends Activity {
  points: CalPoint[];
  certificates: CalCertificate[];
  standards: {
    id: string; standard_id: string; standard_code: string; standard_description: string; used_on: string;
    standard_status: string; is_exception: boolean; exception_reason: string | null; valid_until: string | null;
  }[];
  history: { id: string; from_status: string | null; to_status: string; comment: string | null;
    changed_by_name: string | null; changed_at: string }[];
  missing_requirements: string[];
  requirements: Record<string, boolean | string>;
  computed_result: CalResult | null;
}

export interface CalOverview {
  as_of: string;
  gages_overdue: number;
  gages_due_soon: number;
  gages_in_calibration: number;
  pending: number;
  in_progress: number;
  pending_review: number;
  pending_approval: number;
  pending_release: number;
  unplanned_due: Gage[];
}

export interface CalendarEvent {
  date: string;
  kind: "activity" | "due";
  id?: string;
  code?: string;
  gage_id: string;
  gage_code: string;
  activity_type?: ActivityType;
  status: string;
}

// ---------------------------------------------------------------- laboratory

export interface LabService {
  id: string;
  code: string;
  name: string;
  description: string | null;
  standard_hours: string;
  required_activity: string;
  requires_inspection: boolean;
  is_active: boolean;
}

export type Priority = "LOW" | "NORMAL" | "HIGH" | "URGENT";

export interface ServiceRequest {
  id: string;
  request_code: string;
  plant_id: string;
  department_id: string | null;
  requester_name: string | null;
  customer_type: "INTERNAL" | "EXTERNAL";
  customer_name: string | null;
  service_id: string;
  service_name: string;
  part_number: string | null;
  part_revision: string | null;
  quantity: number;
  description: string;
  priority: Priority;
  requested_date: string;
  committed_date: string | null;
  status: "SUBMITTED" | "APPROVED" | "REJECTED" | "IN_PROGRESS" | "COMPLETED" | "CANCELLED";
  decision_comment: string | null;
  created_at: string;
  work_order_id: string | null;
  work_order_code: string | null;
}

export interface WorkOrder {
  id: string;
  work_order_code: string;
  service_request_id: string;
  request_code: string;
  service_name: string;
  part_number: string | null;
  plant_id: string;
  status: "PENDING" | "SCHEDULED" | "IN_PROGRESS" | "COMPLETED" | "CANCELLED";
  priority: Priority;
  planned_hours: string;
  technician_id: string | null;
  technician_name: string | null;
  scheduled_start: string | null;
  scheduled_end: string | null;
  started_at: string | null;
  completed_at: string | null;
  due_date: string | null;
  overdue: boolean;
  observations: string | null;
  cancel_reason: string | null;
}

export interface InspectionResult {
  id: string;
  part_number: string;
  drawing_revision: string | null;
  sample_id: string | null;
  characteristic_number: string;
  characteristic: string;
  nominal: string;
  lower_limit: string;
  upper_limit: string;
  measured: string;
  unit: string;
  gage_id: string;
  gage_code: string | null;
  gage_status: string;
  measured_at: string;
  result: "OK" | "NOK";
  superseded: boolean;
  correction_reason: string | null;
}

export interface MeasurementReport {
  id: string;
  work_order_id: string;
  report_code: string;
  revision: number;
  status: "ISSUED" | "SUPERSEDED";
  acceptance: "ACCEPTED" | "REJECTED";
  snapshot: {
    work_order: string; request: string; service: string; part_number: string | null; part_revision: string | null;
    customer: string | null; technician: string | null; reviewer: string | null; issued_on: string;
    equipment: string[];
    results: { part_number: string; number: string; characteristic: string; nominal: string; lower: string;
      upper: string; measured: string; unit: string; gage: string | null; result: "OK" | "NOK"; sample: string | null }[];
  };
  observations: string | null;
  revision_reason: string | null;
  issued_at: string;
  attachment_id: string;
}

export interface WorkOrderDetail extends WorkOrder {
  request: ServiceRequest;
  requires_inspection: boolean;
  required_activity: string;
  equipment: { id: string; gage_code: string; description: string; status: GageStatus; next_due_date: string | null }[];
  results: InspectionResult[];
  events: { from_status: string | null; to_status: string; comment: string | null; changed_by_name: string | null;
    changed_at: string }[];
  reports: MeasurementReport[];
}

export interface LabDashboard {
  as_of: string;
  pending_requests: number;
  work_orders: Record<string, number>;
  open_work_orders: number;
  overdue_work_orders: number;
  completed_last_30_days: number;
  on_time_rate_30_days: number | null;
  avg_response_hours_90_days: number | null;
  completed_sample_90_days: number;
  workload_next_7_days: { technician_id: string; technician: string; work_orders: number; planned_hours: number }[];
  capacity: { working_days: number; technicians: number; hours_per_day: number; capacity_hours: number;
    planned_hours: number; utilization_pct: number | null };
}

export interface NotificationT {
  id: string;
  kind: string;
  title: string;
  body: string | null;
  link: string | null;
  created_at: string;
  read_at: string | null;
}
