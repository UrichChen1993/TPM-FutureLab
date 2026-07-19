from datetime import datetime

from domain.models import IoTEvent, MedicationPlan
from rules.proactive_engine import (
    build_proactive_message,
    maybe_trigger_proactive_message,
    maybe_trigger_time_based_checkin,
)


def make_meal_event(event_id: str = "evt-001") -> IoTEvent:
    return IoTEvent(
        user_id="user-001", event_id=event_id, event_type="MEAL_AREA_PRESENCE",
        occurred_at=datetime(2026, 7, 17, 18, 0), payload={"zone": "dining_table"},
    )


def make_plan(
    confirmed: bool = True,
    timing: str = "AFTER_MEAL",
    active: bool = True,
    valid_to: datetime | None = None,
) -> MedicationPlan:
    now = datetime(2026, 7, 17, 17, 30)
    return MedicationPlan(
        med_id="med-001", user_id="user-001", name="脈康錠 5mg", dose="1顆",
        timing=timing, valid_from=now, valid_to=valid_to, confirmed=confirmed,
        created_by="family-001", updated_at=now, active=active,
    )


def test_build_proactive_message_for_meal_area_event_asks_a_question():
    message = build_proactive_message(make_meal_event())

    assert message == "王伯伯，您吃完晚餐了嗎？"
    assert "已經吃" not in message  # must ask, not assert the meal already happened


def test_build_proactive_message_names_confirmed_after_meal_medication():
    message = build_proactive_message(make_meal_event(), [make_plan()])

    assert message == (
        "王伯伯，您吃完晚餐了嗎？ "
        "吃完後請依已確認藥單服用：脈康錠 5mg 1顆。"
    )


def test_build_proactive_message_does_not_use_unconfirmed_ocr_candidate():
    message = build_proactive_message(make_meal_event(), [make_plan(confirmed=False)])

    assert message == "王伯伯，您吃完晚餐了嗎？"
    assert "脈康錠" not in message


def test_build_proactive_message_only_lists_after_meal_medication():
    message = build_proactive_message(make_meal_event(), [make_plan(timing="BEFORE_MEAL")])

    assert message == "王伯伯，您吃完晚餐了嗎？"


def test_build_proactive_message_excludes_inactive_or_expired_medication():
    event = make_meal_event()
    inactive = make_plan(active=False)
    expired = make_plan(valid_to=datetime(2026, 7, 17, 17, 59))

    message = build_proactive_message(event, [inactive, expired])

    assert message == "王伯伯，您吃完晚餐了嗎？"


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


def test_maybe_trigger_time_based_checkin_fires_on_window_start():
    now = datetime(2026, 7, 17, 18, 0)
    asked_dates: set[str] = set()

    message = maybe_trigger_time_based_checkin(now, asked_dates)

    assert message == "王伯伯，您吃完晚餐了嗎？"
    assert asked_dates == {"2026-07-17"}


def test_maybe_trigger_time_based_checkin_does_not_repeat_same_day():
    asked_dates: set[str] = set()
    maybe_trigger_time_based_checkin(datetime(2026, 7, 17, 18, 0), asked_dates)

    second = maybe_trigger_time_based_checkin(datetime(2026, 7, 17, 18, 30), asked_dates)

    assert second is None
    assert asked_dates == {"2026-07-17"}


def test_maybe_trigger_time_based_checkin_ignores_time_before_window():
    message = maybe_trigger_time_based_checkin(datetime(2026, 7, 17, 17, 59), set())

    assert message is None


def test_maybe_trigger_time_based_checkin_ignores_time_at_or_after_window_end():
    message = maybe_trigger_time_based_checkin(datetime(2026, 7, 17, 19, 0), set())

    assert message is None


def test_maybe_trigger_time_based_checkin_fires_again_on_a_new_day():
    asked_dates = {"2026-07-17"}

    message = maybe_trigger_time_based_checkin(datetime(2026, 7, 18, 18, 0), asked_dates)

    assert message == "王伯伯，您吃完晚餐了嗎？"
    assert asked_dates == {"2026-07-17", "2026-07-18"}
