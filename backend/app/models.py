"""Imports every model so Alembic and SQLAlchemy see the full metadata."""

from app.core.sequences import CodeSequence  # noqa: F401
from app.modules.audit.models import AuditEvent  # noqa: F401
from app.modules.calibration.models import (  # noqa: F401
    CalibrationActivity,
    CalibrationCertificate,
    CalibrationPoint,
    CalibrationSetting,
    CalibrationStandardUsage,
    CalibrationStatusHistory,
)
from app.modules.competency.models import Authorization, Competency, CompetencyRecord, PersonnelProfile  # noqa: F401
from app.modules.documents.models import Attachment  # noqa: F401
from app.modules.gages.models import Gage, GageMovement, GageStatusHistory, GageType  # noqa: F401
from app.modules.identity.models import OrganizationMembership, Permission, Role, User  # noqa: F401
from app.modules.laboratory.models import (  # noqa: F401
    InspectionResult,
    LabService,
    LabSettings,
    MeasurementReport,
    ServiceRequest,
    TechnicianAbsence,
    WorkOrder,
    WorkOrderEvent,
)
from app.modules.notifications.models import Notification, NotificationPreference  # noqa: F401
from app.modules.organizations.models import Department, Organization, Plant  # noqa: F401
from app.modules.standards.models import Standard, StandardCertificate  # noqa: F401
