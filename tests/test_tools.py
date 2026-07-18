from datetime import datetime

from agent.tools import build_tools
from domain.models import DoseRecord, MedicationPlan, VitalReading
from domain.states import DoseStatus
from simulator.clock import SimClock
from storage.memory_backend import InMemoryRepository


def make_repo_with_fixtures(now: datetime) -> InMemoryRepository:
    repo = InMemoryRepository()
    repo.seed_medication_plan(MedicationPlan(
        med_id="med-001", user_id="user-001", name="脈康錠 5mg", dose="1顆",
        timing="AFTER_MEAL", valid_from=now, valid_to=None,
        confirmed=True, created_by="family-001", updated_at=now,
    ))
    repo.put_vital(VitalReading(
        user_id="user-001", systolic=120, diastolic=80, heart_rate=72, measured_at=now,
    ))
    repo.put_dose_record(DoseRecord(
        user_id="user-001", date=now.strftime("%Y-%m-%d"), med_id="med-001", slot="DINNER",
        status=DoseStatus.DUE, due_at=now,
    ))
    return repo


def get_tool(tools, name):
    return next(t for t in tools if t.name == name)


def test_get_current_vitals_reports_risk_level():
    now = datetime(2026, 7, 17, 18, 0)
    repo = make_repo_with_fixtures(now)
    clock = SimClock.starting_at(now)
    tools = build_tools(repo, clock, "user-001")

    result = get_tool(tools, "get_current_vitals").invoke({})

    assert result["available"] is True
    assert result["risk_level"] == "safe"


def test_get_medication_plan_returns_confirmed_only():
    now = datetime(2026, 7, 17, 18, 0)
    repo = make_repo_with_fixtures(now)
    clock = SimClock.starting_at(now)
    tools = build_tools(repo, clock, "user-001")

    result = get_tool(tools, "get_medication_plan").invoke({})

    assert result == [{"med_id": "med-001", "name": "脈康錠 5mg", "dose": "1顆", "timing": "AFTER_MEAL"}]


def test_record_dose_self_report_updates_status():
    now = datetime(2026, 7, 17, 18, 0)
    repo = make_repo_with_fixtures(now)
    clock = SimClock.starting_at(now)
    tools = build_tools(repo, clock, "user-001")

    result = get_tool(tools, "record_dose_self_report").invoke({"med_id": "med-001", "slot": "DINNER"})

    assert result == {"ok": True, "status": "self_reported"}
    stored = repo.get_dose_record("user-001", "2026-07-17", "med-001", "DINNER")
    assert stored.status == DoseStatus.SELF_REPORTED
    assert stored.confidence == "self_reported"


def test_get_dose_history_lists_today():
    now = datetime(2026, 7, 17, 18, 0)
    repo = make_repo_with_fixtures(now)
    clock = SimClock.starting_at(now)
    tools = build_tools(repo, clock, "user-001")

    result = get_tool(tools, "get_dose_history").invoke({})

    assert result == [{"med_id": "med-001", "slot": "DINNER", "status": "due", "due_at": now.isoformat()}]
