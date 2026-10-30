export type GageStatus =
  | "CALIBRATED"
  | "DUE_SOON"
  | "OVERDUE"
  | "OUT_OF_SERVICE"
  | "IN_CALIBRATION"
  | "INACTIVE";

export * from "./types-modules";

export type ControlStatus ="ACTIVE" | "OUT_OF_SERVICE" | "IN_CALIBRATION" | "INACTIVE";

export interface Ref {
  id: string;
  code: string;
  name: string;
}

export interface Membership {
  organization_id: string;
  organization_name: string;
  role_code: string;
  role_name: string;
  permissions: string[];
  plants: Ref[];
}

export interface Me {
  id: string;
  email: string;
  full_name: string;
  preferred_language: "es" | "en";
  memberships: Membership[];
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  due_soon_days: number;
  timezone: string;
}

export interface Plant extends Ref {
  is_active: boolean;
}

export interface Department extends Ref {
  plant_id: string;
  is_active: boolean;
}

export interface GageType extends Ref {
  description: string | null;
  default_frequency_days: number | null;
  is_active: boolean;
}

export interface Gage {
  id: string;
  gage_code: string;
  description: string;
  gage_type: Ref;
  plant: Ref;
  department: Ref | null;
  responsible: { id: string; full_name: string } | null;
  manufacturer: string | null;
  model: string | null;
  serial_number: string | null;
  range_min: string | null;
  range_max: string | null;
  unit: string | null;
  resolution: string | null;
  accuracy: string | null;
  criticality: "LOW" | "MEDIUM" | "HIGH" | null;
  location: string | null;
  notes: string | null;
  acquisition_date: string | null;
  in_service_date: string | null;
  calibration_frequency_days: number;
  last_calibration_date: string | null;
  last_verification_date: string | null;
  next_due_date: string | null;
  days_to_due: number | null;
  control_status: ControlStatus;
  status: GageStatus;
  available_for_use: boolean;
  retired_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface StatusHistory {
  id: string;
  from_control_status: string | null;
  to_control_status: string;
  from_status: GageStatus | null;
  to_status: GageStatus;
  reason: string | null;
  changed_by_name: string | null;
  changed_at: string;
}

export interface AuditEvent {
  id: string;
  created_at: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  actor_name: string | null;
  changes: Record<string, unknown> | null;
  reason: string | null;
  request_id: string | null;
}

export interface OrgUser {
  id: string;
  email: string;
  full_name: string;
  role_code: string;
  role_name: string;
  is_active: boolean;
  plants: Ref[];
  last_login_at: string | null;
}

export interface Role {
  code: string;
  name: string;
  permissions: string[];
}

export interface DashboardSummary {
  as_of: string;
  due_soon_days: number;
  plant_scope: string[] | null;
  total_in_service: number;
  available: number;
  by_status: Record<GageStatus, number>;
  upcoming: Gage[];
}
