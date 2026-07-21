from enum import Enum


class MealStatus(str, Enum):
    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"
    NOT_EATEN = "not_eaten"
    UNKNOWN = "unknown"


class DoseStatus(str, Enum):
    SCHEDULED = "scheduled"
    DUE = "due"
    REMINDED = "reminded"
    SELF_REPORTED = "self_reported"
    SENSOR_SUPPORTED = "sensor_supported"
    MISSED = "missed"
    NEEDS_REVIEW = "needs_review"


class RiskLevel(str, Enum):
    SAFE = "safe"
    WARNING = "warning"
    DANGER = "danger"
    UNKNOWN = "unknown"


class NotificationSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Display-only Chinese labels; the enum values above stay English for internal
# logic/audit (reason keys, storage) per the status-code convention in PRD.md.
SEVERITY_LABELS = {
    NotificationSeverity.LOW.value: "低",
    NotificationSeverity.MEDIUM.value: "中",
    NotificationSeverity.HIGH.value: "高",
}
