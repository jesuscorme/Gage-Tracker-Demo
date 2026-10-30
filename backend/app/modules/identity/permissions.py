"""Permission catalogue and system roles.

Permissions are the unit checked by the backend. Roles are bundles of permissions.
Each migration seeds a frozen copy of the values it introduces; when adding a
permission here, add a migration that inserts it as well.

Permissions (RBAC) say *which functions* a role may use. Competency authorizations
(app/modules/competency) additionally say *which person* may execute, review or
approve a technical activity. Restricted activities need both.
"""


class P:
    ORG_READ = "organization:read"
    ORG_MANAGE = "organization:manage"
    PLANTS_MANAGE = "plants:manage"
    USERS_READ = "users:read"
    USERS_MANAGE = "users:manage"
    AUDIT_READ = "audit:read"
    GAGE_TYPES_MANAGE = "gage_types:manage"
    GAGES_READ = "gages:read"
    GAGES_CREATE = "gages:create"
    GAGES_UPDATE = "gages:update"
    GAGES_RETIRE = "gages:retire"
    # Put a gage under restriction (Out of Service / In Calibration).
    GAGES_RESTRICT = "gages:restrict"
    # Release a restricted/inactive gage or change data that moves its due date.
    GAGES_RELEASE = "gages:release"
    # Reassign responsible / move between plant, department or location.
    GAGES_TRANSFER = "gages:transfer"
    GAGES_IMPORT = "gages:import"

    CALIBRATION_READ = "calibration:read"
    # Plan, request, schedule, cancel, upload certificates.
    CALIBRATION_MANAGE = "calibration:manage"
    # Start, capture As Found / As Left, submit for review.
    CALIBRATION_EXECUTE = "calibration:execute"
    CALIBRATION_REVIEW = "calibration:review"
    CALIBRATION_APPROVE = "calibration:approve"
    # Release an approved activity into the gage record.
    CALIBRATION_RELEASE = "calibration:release"
    CALIBRATION_SETTINGS = "calibration:settings"

    STANDARDS_READ = "standards:read"
    STANDARDS_MANAGE = "standards:manage"
    # Use an expired/restricted standard under a documented exception.
    STANDARDS_EXCEPTION = "standards:exception"

    COMPETENCY_READ = "competency:read"
    COMPETENCY_MANAGE = "competency:manage"
    COMPETENCY_AUTHORIZE = "competency:authorize"

    LAB_READ = "lab:read"
    LAB_REQUEST = "lab:request"
    # Review requests, create/schedule work orders, services, capacity.
    LAB_MANAGE = "lab:manage"
    LAB_EXECUTE = "lab:execute"
    LAB_REPORT = "lab:report"

    MSA_READ = "msa:read"
    # Create and configure studies, capture and import data.
    MSA_MANAGE = "msa:manage"
    # Run statistical calculations (also needs the MSA_EVALUATION authorization).
    MSA_CALCULATE = "msa:calculate"
    # Review/approve studies and approve acceptance criteria.
    MSA_APPROVE = "msa:approve"
    MSA_CRITERIA = "msa:criteria"

    OOT_READ = "oot:read"
    OOT_MANAGE = "oot:manage"
    # Approve OOT cases and release gages restricted by an OOT case.
    OOT_APPROVE = "oot:approve"

    CONFIG_READ = "config:read"
    CONFIG_MANAGE = "config:manage"
    CONFIG_APPROVE = "config:approve"

    INTEGRATIONS_READ = "integrations:read"
    # API clients, webhooks, devices and import jobs administration.
    INTEGRATIONS_MANAGE = "integrations:manage"
    # Submit device readings (edge connectors).
    CONNECTORS_SUBMIT = "connectors:submit"

    COMPLIANCE_READ = "compliance:read"


PERMISSIONS: dict[str, str] = {
    P.ORG_READ: "View organization, plants and departments",
    P.ORG_MANAGE: "Edit organization settings",
    P.PLANTS_MANAGE: "Create and edit plants and departments",
    P.USERS_READ: "View users of the organization",
    P.USERS_MANAGE: "Invite users, assign roles and plant scope",
    P.AUDIT_READ: "View the audit trail",
    P.GAGE_TYPES_MANAGE: "Manage the gage type catalogue",
    P.GAGES_READ: "View gages",
    P.GAGES_CREATE: "Register gages",
    P.GAGES_UPDATE: "Edit descriptive gage data",
    P.GAGES_RETIRE: "Retire gages (logical deletion)",
    P.GAGES_RESTRICT: "Place gages Out of Service or In Calibration",
    P.GAGES_RELEASE: "Release restricted gages and change calibration dates/frequency",
    P.GAGES_TRANSFER: "Reassign responsible and transfer gages between plants, departments or locations",
    P.GAGES_IMPORT: "Import gage inventory from CSV/Excel",
    P.CALIBRATION_READ: "View calibration and verification activities",
    P.CALIBRATION_MANAGE: "Plan, request, schedule and cancel calibration activities; manage certificates",
    P.CALIBRATION_EXECUTE: "Execute activities and capture As Found / As Left results",
    P.CALIBRATION_REVIEW: "Perform technical review of calibration activities",
    P.CALIBRATION_APPROVE: "Approve calibration activities",
    P.CALIBRATION_RELEASE: "Release approved activities into the gage record",
    P.CALIBRATION_SETTINGS: "Configure enabled activity types and evidence requirements",
    P.STANDARDS_READ: "View reference standards",
    P.STANDARDS_MANAGE: "Register standards and their certificates",
    P.STANDARDS_EXCEPTION: "Authorize use of an expired or restricted standard (documented exception)",
    P.COMPETENCY_READ: "View personnel profiles, competency matrix and authorizations",
    P.COMPETENCY_MANAGE: "Manage personnel profiles, competencies, training and evaluations",
    P.COMPETENCY_AUTHORIZE: "Grant and revoke activity authorizations",
    P.LAB_READ: "View laboratory requests, work orders and reports",
    P.LAB_REQUEST: "Create laboratory service requests",
    P.LAB_MANAGE: "Review requests, create and schedule work orders, manage services and capacity",
    P.LAB_EXECUTE: "Execute work orders and capture measurements",
    P.LAB_REPORT: "Issue measurement reports",
    P.MSA_READ: "View MSA studies, runs and reports",
    P.MSA_MANAGE: "Create and configure MSA studies; capture and import study data",
    P.MSA_CALCULATE: "Run MSA statistical calculations",
    P.MSA_APPROVE: "Review and approve MSA studies; approve acceptance criteria",
    P.MSA_CRITERIA: "Define MSA acceptance criteria",
    P.OOT_READ: "View out-of-tolerance cases",
    P.OOT_MANAGE: "Register and investigate out-of-tolerance cases",
    P.OOT_APPROVE: "Approve and close OOT cases; release gages restricted by OOT",
    P.CONFIG_READ: "View platform configuration",
    P.CONFIG_MANAGE: "Edit custom fields, forms, workflows, approval matrices and business rules",
    P.CONFIG_APPROVE: "Approve configuration changes",
    P.INTEGRATIONS_READ: "View integrations, import history and webhook deliveries",
    P.INTEGRATIONS_MANAGE: "Manage API clients, webhooks, devices and import jobs",
    P.CONNECTORS_SUBMIT: "Submit readings from measurement devices",
    P.COMPLIANCE_READ: "Query compliance evidence and export audit records",
}

_ALL = list(PERMISSIONS)
_READ = [P.ORG_READ, P.USERS_READ, P.GAGES_READ]
_READ_TECH = [P.CALIBRATION_READ, P.STANDARDS_READ, P.COMPETENCY_READ, P.LAB_READ, P.MSA_READ, P.OOT_READ]

SYSTEM_ROLES: dict[str, dict] = {
    "org_admin": {
        "name": "Organization Administrator",
        "permissions": _ALL,
    },
    "metrology_manager": {
        "name": "Metrology Manager",
        "permissions": _READ
        + _READ_TECH
        + [
            P.AUDIT_READ, P.GAGE_TYPES_MANAGE, P.GAGES_CREATE, P.GAGES_UPDATE, P.GAGES_RETIRE,
            P.GAGES_RESTRICT, P.GAGES_RELEASE, P.GAGES_TRANSFER, P.GAGES_IMPORT,
            P.CALIBRATION_MANAGE, P.CALIBRATION_EXECUTE, P.CALIBRATION_REVIEW, P.CALIBRATION_APPROVE,
            P.CALIBRATION_RELEASE, P.CALIBRATION_SETTINGS,
            P.STANDARDS_MANAGE, P.STANDARDS_EXCEPTION,
            P.COMPETENCY_MANAGE, P.COMPETENCY_AUTHORIZE,
            P.LAB_REQUEST, P.LAB_MANAGE, P.LAB_EXECUTE, P.LAB_REPORT,
            P.MSA_MANAGE, P.MSA_CALCULATE, P.MSA_APPROVE, P.MSA_CRITERIA,
            P.OOT_MANAGE, P.OOT_APPROVE,
            P.CONFIG_READ, P.CONFIG_MANAGE, P.CONFIG_APPROVE,
            P.INTEGRATIONS_READ, P.INTEGRATIONS_MANAGE, P.COMPLIANCE_READ,
        ],
    },
    "metrology_technician": {
        "name": "Metrology Technician",
        "permissions": _READ
        + _READ_TECH
        + [P.GAGES_CREATE, P.GAGES_UPDATE, P.GAGES_RESTRICT, P.CALIBRATION_EXECUTE, P.LAB_EXECUTE,
           P.MSA_MANAGE, P.MSA_CALCULATE, P.OOT_MANAGE],
    },
    "lab_technician": {
        "name": "Laboratory Technician",
        "permissions": _READ + _READ_TECH + [P.LAB_EXECUTE],
    },
    "requester": {
        "name": "Laboratory Requester",
        "permissions": [P.ORG_READ, P.GAGES_READ, P.LAB_READ, P.LAB_REQUEST],
    },
    "auditor": {
        "name": "Auditor (read only)",
        "permissions": _READ + _READ_TECH + [P.AUDIT_READ, P.CONFIG_READ, P.INTEGRATIONS_READ, P.COMPLIANCE_READ],
    },
    "viewer": {
        "name": "Viewer",
        "permissions": [P.ORG_READ, P.GAGES_READ, P.CALIBRATION_READ, P.STANDARDS_READ, P.LAB_READ, P.MSA_READ,
                        P.OOT_READ],
    },
    # Service account of an Edge Connector: reads gages and submits device readings.
    "edge_agent": {
        "name": "Edge Connector (service account)",
        "permissions": [P.GAGES_READ, P.CONNECTORS_SUBMIT],
    },
}
