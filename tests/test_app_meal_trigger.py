from datetime import datetime

from app import confirm_scanned_prescription, trigger_meal_event, trigger_prescription_scan
from simulator.clock import SimClock
from simulator.prescription_ocr import review_ocr_candidate
from storage.memory_backend import InMemoryRepository


def test_meal_event_trigger_adds_proactive_chat_message():
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))
    messages: list[tuple[str, str]] = []
    asked_event_ids: set[str] = set()

    result = trigger_prescription_scan(clock, messages=[])
    review_ocr_candidate(result, "med-001")
    confirm_scanned_prescription(repo, result, "user-001", messages=[])
    trigger_meal_event(repo, clock, "user-001", messages, asked_event_ids)

    assert messages == [(
        "ai",
        "王伯伯，您吃完晚餐了嗎？ "
        "吃完後請依已確認藥單服用：脈優錠 5mg 1顆（每日1次）。",
    )]
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


def test_scan_then_confirm_adds_auditable_chat_messages_and_plan():
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))
    messages: list[tuple[str, str]] = []

    result = trigger_prescription_scan(clock, messages)
    review_ocr_candidate(result, "med-001")
    confirm_scanned_prescription(repo, result, "user-001", messages)

    assert messages[0] == ("human", "📷（示範藥單，執行模擬 OCR）")
    assert "OCR 辨識完成（模擬）" in messages[1][1]
    assert "待家屬確認" in messages[1][1]
    assert "家屬已確認藥單" in messages[2][1]
    assert repo.get_medication_plans("user-001")[0].confirmed is True
    assert len(repo.list_medication_audit_events("user-001")) == 3
