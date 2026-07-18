import uuid

from domain.models import DoseRecord, IoTEvent
from domain.states import DoseStatus


def simulate_meal_area_event(repo, clock, user_id: str) -> IoTEvent:
    event = IoTEvent(
        user_id=user_id, event_id=f"evt-{uuid.uuid4().hex[:8]}",
        event_type="MEAL_AREA_PRESENCE", occurred_at=clock.now, payload={"zone": "dining_table"},
    )
    repo.put_iot_event(event)
    return event


def simulate_pillbox_event(
    repo, clock, user_id: str, med_id: str, slot: str
) -> tuple[IoTEvent, DoseRecord | None]:
    event = IoTEvent(
        user_id=user_id, event_id=f"evt-{uuid.uuid4().hex[:8]}",
        event_type="PILLBOX_OPENED_WEIGHT_DROP", occurred_at=clock.now,
        payload={"med_id": med_id, "slot": slot},
    )
    repo.put_iot_event(event)

    today = clock.now.strftime("%Y-%m-%d")
    record = repo.get_dose_record(user_id, today, med_id, slot)
    if record is not None and record.status != DoseStatus.SENSOR_SUPPORTED:
        record.status = DoseStatus.SENSOR_SUPPORTED
        record.confidence = "sensor_supported"
        record.completed_at = clock.now
        record.source = f"{record.source}+sensor" if record.source else "sensor"
        repo.put_dose_record(record)
    return event, record
