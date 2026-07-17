from datetime import datetime

from domain.states import RiskLevel
from rules.config import (
    BP_DIASTOLIC_DANGER_HIGH,
    BP_SYSTOLIC_DANGER_HIGH,
    BP_SYSTOLIC_DANGER_LOW,
    BP_SYSTOLIC_WARNING_HIGH,
    DANGER_SYMPTOMS,
    HR_DANGER_HIGH,
    HR_DANGER_LOW,
    HR_WARNING_HIGH,
    HR_WARNING_LOW,
    VITAL_STALE_MINUTES,
)


def classify_vitals(
    systolic: int, diastolic: int, heart_rate: int, measured_at: datetime, now: datetime
) -> RiskLevel:
    age_minutes = (now - measured_at).total_seconds() / 60
    if age_minutes > VITAL_STALE_MINUTES:
        return RiskLevel.UNKNOWN

    if (
        systolic >= BP_SYSTOLIC_DANGER_HIGH
        or systolic <= BP_SYSTOLIC_DANGER_LOW
        or diastolic >= BP_DIASTOLIC_DANGER_HIGH
        or heart_rate >= HR_DANGER_HIGH
        or heart_rate <= HR_DANGER_LOW
    ):
        return RiskLevel.DANGER

    if systolic >= BP_SYSTOLIC_WARNING_HIGH or heart_rate >= HR_WARNING_HIGH or heart_rate <= HR_WARNING_LOW:
        return RiskLevel.WARNING

    return RiskLevel.SAFE


def has_danger_symptom(reported_text: str) -> bool:
    return any(keyword in reported_text for keyword in DANGER_SYMPTOMS)


def combine_risk(vitals_risk: RiskLevel, danger_symptom_confirmed: bool) -> RiskLevel:
    if danger_symptom_confirmed:
        return RiskLevel.DANGER
    if vitals_risk == RiskLevel.UNKNOWN:
        return RiskLevel.WARNING
    return vitals_risk
