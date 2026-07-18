from datetime import datetime

from domain.models import DoseRecord
from domain.states import DoseStatus
from simulator.clock import SimClock
from simulator.iot_simulator import simulate_meal_area_event, simulate_pillbox_event
from storage.memory_backend import InMemoryRepository


def test_simulate_meal_area_event_is_recorded():
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 18, 0))

    event = simulate_meal_area_event(repo, clock, "user-001")

    assert event.event_type == "MEAL_AREA_PRESENCE"


def test_simulate_pillbox_event_upgrades_dose_to_sensor_supported():
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 18, 30))
    repo.put_dose_record(DoseRecord(
        user_id="user-001", date="2026-07-17", med_id="med-001", slot="DINNER",
        status=DoseStatus.SELF_REPORTED, due_at=datetime(2026, 7, 17, 18, 0), source="voice",
    ))

    event, record = simulate_pillbox_event(repo, clock, "user-001", "med-001", "DINNER")

    assert event.event_type == "PILLBOX_OPENED_WEIGHT_DROP"
    assert record.status == DoseStatus.SENSOR_SUPPORTED
    assert record.source == "voice+sensor"
