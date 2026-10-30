"""Permission catalogue and system roles.

Permissions are the unit checked by the backend. Roles are bundles of permissions.
The migration ``0001`` seeds a frozen copy of these values; when adding a permission
here, add a migration that inserts it as well.
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
}

_ALL = list(PERMISSIONS)
_READ = [P.ORG_READ, P.USERS_READ, P.GAGES_READ]

SYSTEM_ROLES: dict[str, dict] = {
    "org_admin": {
        "name": "Organization Administrator",
        "permissions": _ALL,
    },
    "metrology_manager": {
        "name": "Metrology Manager",
        "permissions": _READ
        + [
            P.AUDIT_READ,
            P.GAGE_TYPES_MANAGE,
            P.GAGES_CREATE,
            P.GAGES_UPDATE,
            P.GAGES_RETIRE,
            P.GAGES_RESTRICT,
            P.GAGES_RELEASE,
        ],
    },
    "metrology_technician": {
        "name": "Metrology Technician",
        "permissions": _READ + [P.GAGES_CREATE, P.GAGES_UPDATE, P.GAGES_RESTRICT],
    },
    "auditor": {
        "name": "Auditor (read only)",
        "permissions": _READ + [P.AUDIT_READ],
    },
    "viewer": {
        "name": "Viewer",
        "permissions": [P.ORG_READ, P.GAGES_READ],
    },
}
