from datetime import datetime

from app import trigger_meal_event
from simulator.clock import SimClock
from storage.memory_backend import InMemoryRepository


def test_meal_event_trigger_adds_proactive_chat_message():
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))
    messages: list[tuple[str, str]] = []
    asked_event_ids: set[str] = set()

    trigger_meal_event(repo, clock, "user-001", messages, asked_event_ids)

    assert messages == [("ai", "王伯伯，您吃完晚餐了嗎？")]
    assert len(asked_event_ids) == 1


def test_meal_event_trigger_advances_clock_to_dinner_time():
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 15, 0))

    trigger_meal_event(repo, clock, "user-001", [], set())

    assert clock.now.hour == 18


def test_meal_event_trigger_does_not_duplicate_message_on_repeated_call_with_same_ids():
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))
    messages: list[tuple[str, str]] = []
    asked_event_ids: set[str] = set()

    trigger_meal_event(repo, clock, "user-001", messages, asked_event_ids)
    first_event_id = next(iter(asked_event_ids))
    # Re-simulate the dedup guard directly: a second trigger for an event
    # already in asked_event_ids must not add a second chat message.
    from rules.proactive_engine import maybe_trigger_proactive_message
    from domain.models import IoTEvent

    replay = IoTEvent(
        user_id="user-001", event_id=first_event_id, event_type="MEAL_AREA_PRESENCE",
        occurred_at=clock.now, payload={},
    )
    result = maybe_trigger_proactive_message(replay, asked_event_ids)

    assert result is None
    assert len(messages) == 1
