from datetime import datetime

from domain.models import (
    DoseRecord,
    MedicationPlan,
    MedicationPlanAuditEvent,
    Notification,
    VitalReading,
)
from domain.states import DoseStatus
from storage.memory_backend import InMemoryRepository


def make_plan():
    now = datetime(2026, 7, 17, 8, 0)
    return MedicationPlan(
        med_id="med-001", user_id="user-001", name="脈康錠 5mg", dose="1顆",
        timing="AFTER_DINNER", valid_from=now, valid_to=None,
        confirmed=True, created_by="family-001", updated_at=now,
    )


def test_seed_and_get_medication_plans():
    repo = InMemoryRepository()
    repo.seed_medication_plan(make_plan())
    plans = repo.get_medication_plans("user-001")
    assert len(plans) == 1
    assert plans[0].med_id == "med-001"


def test_latest_vital_returns_most_recent():
    repo = InMemoryRepository()
    repo.put_vital(VitalReading(
        user_id="user-001", systolic=120, diastolic=80, heart_rate=70,
        measured_at=datetime(2026, 7, 17, 17, 0),
    ))
    repo.put_vital(VitalReading(
        user_id="user-001", systolic=125, diastolic=82, heart_rate=72,
        measured_at=datetime(2026, 7, 17, 18, 0),
    ))
    latest = repo.get_latest_vital("user-001")
    assert latest.measured_at == datetime(2026, 7, 17, 18, 0)


def test_dose_record_round_trip():
    repo = InMemoryRepository()
    record = DoseRecord(
        user_id="user-001", date="2026-07-17", med_id="med-001", slot="DINNER",
        status=DoseStatus.SCHEDULED, due_at=datetime(2026, 7, 17, 18, 0),
    )
    repo.put_dose_record(record)
    fetched = repo.get_dose_record("user-001", "2026-07-17", "med-001", "DINNER")
    assert fetched.status == DoseStatus.SCHEDULED
    assert repo.list_dose_records("user-001", "2026-07-17") == [fetched]


def test_notifications_accumulate():
    repo = InMemoryRepository()
    repo.put_notification(Notification(
        user_id="user-001", notification_id="n1", occurred_at=datetime(2026, 7, 17, 19, 0),
        reason="dose_missed", severity="medium", message="漏服",
    ))
    assert len(repo.list_notifications("user-001")) == 1


def test_medication_audit_events_are_append_only_and_filterable():
    repo = InMemoryRepository()
    repo.put_medication_audit_event(MedicationPlanAuditEvent(
        event_id="audit-001", user_id="user-001", med_id="med-001",
        action="PLAN_CONFIRMED", actor_id="family-001",
        occurred_at=datetime(2026, 7, 17, 17, 30), after={"confirmed": True},
    ))
    repo.put_medication_audit_event(MedicationPlanAuditEvent(
        event_id="audit-002", user_id="user-001", med_id="med-002",
        action="PLAN_CONFIRMED", actor_id="family-002",
        occurred_at=datetime(2026, 7, 17, 17, 31), after={"confirmed": True},
    ))

    assert len(repo.list_medication_audit_events("user-001")) == 2
    filtered = repo.list_medication_audit_events("user-001", "med-001")
    assert [event.event_id for event in filtered] == ["audit-001"]
