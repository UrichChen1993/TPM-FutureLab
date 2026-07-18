from datetime import datetime

from domain.models import IoTEvent
from rules.proactive_engine import build_proactive_message, maybe_trigger_proactive_message


def make_meal_event(event_id: str = "evt-001") -> IoTEvent:
    return IoTEvent(
        user_id="user-001", event_id=event_id, event_type="MEAL_AREA_PRESENCE",
        occurred_at=datetime(2026, 7, 17, 18, 0), payload={"zone": "dining_table"},
    )


def test_build_proactive_message_for_meal_area_event_asks_a_question():
    message = build_proactive_message(make_meal_event())

    assert message == "王伯伯，您吃完晚餐了嗎？"
    assert "已經吃" not in message  # must ask, not assert the meal already happened


def test_build_proactive_message_returns_none_for_unrelated_event_type():
    event = IoTEvent(
        user_id="user-001", event_id="evt-002", event_type="PILLBOX_OPENED_WEIGHT_DROP",
        occurred_at=datetime(2026, 7, 17, 18, 30), payload={},
    )

    assert build_proactive_message(event) is None


def test_maybe_trigger_proactive_message_fires_once_per_event_id():
    event = make_meal_event()
    asked: set[str] = set()

    first = maybe_trigger_proactive_message(event, asked)
    second = maybe_trigger_proactive_message(event, asked)

    assert first == "王伯伯，您吃完晚餐了嗎？"
    assert second is None
    assert asked == {"evt-001"}


def test_maybe_trigger_proactive_message_fires_independently_for_distinct_events():
    asked: set[str] = set()

    first = maybe_trigger_proactive_message(make_meal_event("evt-001"), asked)
    second = maybe_trigger_proactive_message(make_meal_event("evt-002"), asked)

    assert first == "王伯伯，您吃完晚餐了嗎？"
    assert second == "王伯伯，您吃完晚餐了嗎？"
