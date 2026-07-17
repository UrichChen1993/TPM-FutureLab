from datetime import datetime

from domain.states import RiskLevel
from rules.risk_engine import classify_vitals, combine_risk, has_danger_symptom


def test_normal_vitals_are_safe():
    now = datetime(2026, 7, 17, 18, 0)
    risk = classify_vitals(120, 80, 70, measured_at=now, now=now)
    assert risk == RiskLevel.SAFE


def test_high_heart_rate_is_danger():
    now = datetime(2026, 7, 17, 18, 0)
    risk = classify_vitals(120, 80, 130, measured_at=now, now=now)
    assert risk == RiskLevel.DANGER


def test_borderline_systolic_is_warning():
    now = datetime(2026, 7, 17, 18, 0)
    risk = classify_vitals(165, 80, 70, measured_at=now, now=now)
    assert risk == RiskLevel.WARNING


def test_stale_vitals_are_unknown():
    measured_at = datetime(2026, 7, 17, 16, 0)
    now = datetime(2026, 7, 17, 18, 0)
    risk = classify_vitals(120, 80, 70, measured_at=measured_at, now=now)
    assert risk == RiskLevel.UNKNOWN


def test_has_danger_symptom_detects_keyword():
    assert has_danger_symptom("我有胸痛的感覺") is True
    assert has_danger_symptom("只是有點累") is False


def test_combine_risk_danger_symptom_overrides():
    assert combine_risk(RiskLevel.SAFE, danger_symptom_confirmed=True) == RiskLevel.DANGER


def test_combine_risk_unknown_vitals_falls_back_to_warning():
    assert combine_risk(RiskLevel.UNKNOWN, danger_symptom_confirmed=False) == RiskLevel.WARNING
