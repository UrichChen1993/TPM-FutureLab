from dataclasses import dataclass, field
from datetime import datetime

from domain.states import DoseStatus


@dataclass
class MedicationPlan:
    med_id: str
    user_id: str
    name: str
    dose: str
    timing: str  # "BEFORE_MEAL" | "AFTER_MEAL" | "FIXED_TIME"
    valid_from: datetime
    valid_to: datetime | None
    confirmed: bool
    created_by: str
    updated_at: datetime


@dataclass
class VitalReading:
    user_id: str
    systolic: int
    diastolic: int
    heart_rate: int
    measured_at: datetime
    source: str = "simulated_device"


@dataclass
class IoTEvent:
    user_id: str
    event_id: str
    event_type: str  # "MEAL_AREA_PRESENCE" | "PILLBOX_OPENED_WEIGHT_DROP"
    occurred_at: datetime
    payload: dict = field(default_factory=dict)


@dataclass
class DoseRecord:
    user_id: str
    date: str  # "YYYY-MM-DD"
    med_id: str
    slot: str  # "BREAKFAST" | "LUNCH" | "DINNER"
    status: DoseStatus
    due_at: datetime
    reminded_at: datetime | None = None
    completed_at: datetime | None = None
    source: str | None = None       # "voice" | "sensor" | "voice+sensor"
    confidence: str | None = None   # "self_reported" | "sensor_supported"


@dataclass
class Notification:
    user_id: str
    notification_id: str
    occurred_at: datetime
    reason: str
    severity: str  # NotificationSeverity value
    message: str
