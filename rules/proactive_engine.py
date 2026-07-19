from datetime import datetime, time as dt_time

from domain.models import IoTEvent, MedicationPlan

MEAL_CHECKIN_MESSAGE = "王伯伯，您吃完晚餐了嗎？"
DINNER_WINDOW_START = dt_time(18, 0)
DINNER_WINDOW_END = dt_time(19, 0)


def _active_after_meal_plans(
    event: IoTEvent, medication_plans: list[MedicationPlan]
) -> list[MedicationPlan]:
    return [
        plan
        for plan in medication_plans
        if plan.is_active_at(event.occurred_at)
        and plan.timing == "AFTER_MEAL"
    ]


def build_proactive_message(
    event: IoTEvent, medication_plans: list[MedicationPlan] | None = None
) -> str | None:
    if event.event_type == "MEAL_AREA_PRESENCE":
        plans = _active_after_meal_plans(event, medication_plans or [])
        if not plans:
            return MEAL_CHECKIN_MESSAGE
        medication_text = "、".join(
            f"{plan.name} {plan.dose}"
            + (f"（{plan.frequency}）" if plan.frequency else "")
            for plan in plans
        )
        return f"{MEAL_CHECKIN_MESSAGE} 吃完後請依已確認藥單服用：{medication_text}。"
    return None


def maybe_trigger_proactive_message(
    event: IoTEvent,
    asked_event_ids: set[str],
    medication_plans: list[MedicationPlan] | None = None,
) -> str | None:
    if event.event_id in asked_event_ids:
        return None
    message = build_proactive_message(event, medication_plans)
    if message is not None:
        asked_event_ids.add(event.event_id)
    return message


def maybe_trigger_time_based_checkin(now: datetime, asked_dates: set[str]) -> str | None:
    date_key = now.strftime("%Y-%m-%d")
    if date_key in asked_dates:
        return None
    if not (DINNER_WINDOW_START <= now.time() < DINNER_WINDOW_END):
        return None
    asked_dates.add(date_key)
    return MEAL_CHECKIN_MESSAGE
