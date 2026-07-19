from datetime import datetime, timedelta

from domain.models import DoseRecord, MedicationPlan
from domain.states import DoseStatus
from rules.escalation_engine import apply_escalation, ensure_today_doses, evaluate_dose
from simulator.clock import SimClock
from storage.memory_backend import InMemoryRepository


def make_record(status=DoseStatus.SCHEDULED, due_at=None, reminded_at=None):
    return DoseRecord(
        user_id="user-001", date="2026-07-17", med_id="med-001", slot="DINNER",
        status=status, due_at=due_at or datetime(2026, 7, 17, 18, 0), reminded_at=reminded_at,
    )


def test_before_due_stays_scheduled():
    record = make_record()
    now = datetime(2026, 7, 17, 17, 0)
    result = evaluate_dose(record, now)
    assert result.new_status == DoseStatus.SCHEDULED
    assert result.send_reminder is False


def test_at_due_time_becomes_due():
    record = make_record()
    now = datetime(2026, 7, 17, 18, 0)
    result = evaluate_dose(record, now)
    assert result.new_status == DoseStatus.DUE


def test_20_minutes_after_due_sends_first_reminder():
    record = make_record(status=DoseStatus.DUE)
    now = datetime(2026, 7, 17, 18, 20)
    result = evaluate_dose(record, now)
    assert result.new_status == DoseStatus.REMINDED
    assert result.send_reminder is True


def test_60_minutes_after_due_is_missed_with_medium_notification():
    record = make_record(status=DoseStatus.REMINDED, reminded_at=datetime(2026, 7, 17, 18, 40))
    now = datetime(2026, 7, 17, 19, 0)
    result = evaluate_dose(record, now)
    assert result.new_status == DoseStatus.MISSED
    assert result.notify_severity == "medium"


def test_120_minutes_after_due_escalates_to_high():
    record = make_record(status=DoseStatus.MISSED)
    now = datetime(2026, 7, 17, 20, 0)
    result = evaluate_dose(record, now)
    assert result.new_status == DoseStatus.MISSED
    assert result.notify_severity == "high"


def test_self_reported_dose_has_no_further_action():
    record = make_record(status=DoseStatus.SELF_REPORTED)
    result = evaluate_dose(record, datetime(2026, 7, 17, 23, 0))
    assert result.new_status == DoseStatus.SELF_REPORTED
    assert result.send_reminder is False
    assert result.notify_severity is None


def test_apply_escalation_writes_dose_and_avoids_duplicate_notifications():
    repo = InMemoryRepository()
    record = make_record(status=DoseStatus.REMINDED, reminded_at=datetime(2026, 7, 17, 18, 40))
    repo.put_dose_record(record)
    now = datetime(2026, 7, 17, 19, 0)

    apply_escalation(repo, record, now)
    apply_escalation(repo, record, now)  # second call must not duplicate the notification

    stored = repo.get_dose_record("user-001", "2026-07-17", "med-001", "DINNER")
    assert stored.status == DoseStatus.MISSED
    notifications = repo.list_notifications("user-001")
    assert len(notifications) == 1
    assert "第1次提醒後未回應" in notifications[0].message


def test_high_severity_message_mentions_second_escalation():
    repo = InMemoryRepository()
    record = make_record(status=DoseStatus.MISSED)
    apply_escalation(repo, record, datetime(2026, 7, 17, 20, 0))

    notifications = repo.list_notifications("user-001")
    assert len(notifications) == 1
    assert "第2次提醒後仍未回應" in notifications[0].message


def test_ensure_today_doses_creates_scheduled_record_from_confirmed_plan():
    repo = InMemoryRepository()
    now = datetime(2026, 7, 17, 8, 0)
    repo.seed_medication_plan(MedicationPlan(
        med_id="med-001", user_id="user-001", name="脈康錠 5mg", dose="1顆",
        timing="AFTER_DINNER", valid_from=now, valid_to=None,
        confirmed=True, created_by="family-001", updated_at=now,
    ))
    clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))

    ensure_today_doses(repo, clock, "user-001")

    records = repo.list_dose_records("user-001", "2026-07-17")
    assert len(records) == 1
    assert records[0].slot == "DINNER"
    assert records[0].status == DoseStatus.SCHEDULED
    assert records[0].due_at == datetime(2026, 7, 17, 18, 0)


def test_ensure_today_doses_maps_sleep_and_wake_and_meal_timings_to_slots():
    repo = InMemoryRepository()
    now = datetime(2026, 7, 17, 6, 0)
    for med_id, timing in [
        ("med-wake", "ON_WAKE"),
        ("med-sleep", "BEFORE_SLEEP"),
        ("med-breakfast", "BEFORE_BREAKFAST"),
        ("med-lunch", "AFTER_LUNCH"),
    ]:
        repo.seed_medication_plan(MedicationPlan(
            med_id=med_id, user_id="user-001", name="測試藥", dose="1顆",
            timing=timing, valid_from=now, valid_to=None,
            confirmed=True, created_by="family-001", updated_at=now,
        ))
    clock = SimClock.starting_at(now)

    ensure_today_doses(repo, clock, "user-001")

    records = {r.med_id: (r.slot, r.due_at.time()) for r in repo.list_dose_records("user-001", "2026-07-17")}
    assert records == {
        "med-wake": ("ON_WAKE", datetime(2026, 7, 17, 7, 0).time()),
        "med-sleep": ("BEFORE_SLEEP", datetime(2026, 7, 17, 22, 0).time()),
        "med-breakfast": ("BREAKFAST", datetime(2026, 7, 17, 8, 0).time()),
        "med-lunch": ("LUNCH", datetime(2026, 7, 17, 12, 0).time()),
    }


def test_ensure_today_doses_creates_records_for_each_fixed_time():
    repo = InMemoryRepository()
    now = datetime(2026, 7, 17, 8, 0)
    repo.seed_medication_plan(MedicationPlan(
        med_id="med-fixed", user_id="user-001", name="定時藥物", dose="1顆",
        timing="FIXED_TIME", valid_from=now, valid_to=None,
        confirmed=True, created_by="family-001", updated_at=now,
        fixed_times=("08:30", "20:00"),
    ))
    clock = SimClock.starting_at(datetime(2026, 7, 17, 8, 0))

    ensure_today_doses(repo, clock, "user-001")

    records = sorted(
        repo.list_dose_records("user-001", "2026-07-17"),
        key=lambda record: record.due_at,
    )
    assert [(record.slot, record.due_at.time()) for record in records] == [
        ("FIXED_0830", datetime(2026, 7, 17, 8, 30).time()),
        ("FIXED_2000", datetime(2026, 7, 17, 20, 0).time()),
    ]


def test_apply_escalation_notifies_separately_for_different_dates():
    repo = InMemoryRepository()
    record_day1 = DoseRecord(
        user_id="user-001", date="2026-07-17", med_id="med-001", slot="DINNER",
        status=DoseStatus.REMINDED, due_at=datetime(2026, 7, 17, 18, 0),
        reminded_at=datetime(2026, 7, 17, 18, 40),
    )
    repo.put_dose_record(record_day1)
    apply_escalation(repo, record_day1, datetime(2026, 7, 17, 19, 0))

    record_day2 = DoseRecord(
        user_id="user-001", date="2026-07-18", med_id="med-001", slot="DINNER",
        status=DoseStatus.REMINDED, due_at=datetime(2026, 7, 18, 18, 0),
        reminded_at=datetime(2026, 7, 18, 18, 40),
    )
    repo.put_dose_record(record_day2)
    apply_escalation(repo, record_day2, datetime(2026, 7, 18, 19, 0))

    assert len(repo.list_notifications("user-001")) == 2
