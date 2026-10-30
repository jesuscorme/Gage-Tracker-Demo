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
from app.modules.configuration.models import ConfigItem, ConfigVersion, CustomFieldValue, WorkflowEvent  # noqa: F401,E402
from app.modules.events.models import OutboxEvent  # noqa: F401,E402
from app.modules.integrations.models import (  # noqa: F401,E402
    ApiClient,
    ApiRequestLog,
    Device,
    DeviceReading,
    IdempotencyRecord,
    ImportJob,
    WebhookAttempt,
    WebhookDelivery,
    WebhookEndpoint,
)
from app.modules.msa.models import MsaCriteriaSet, MsaObservation, MsaReport, MsaRun, MsaStudy  # noqa: F401,E402
from app.modules.oot.models import OotAction, OotCase, OotImpactItem, OotSettings  # noqa: F401,E402
