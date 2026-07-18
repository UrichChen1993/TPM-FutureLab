from domain.models import IoTEvent

MEAL_CHECKIN_MESSAGE = "王伯伯，您吃完晚餐了嗎？"


def build_proactive_message(event: IoTEvent) -> str | None:
    if event.event_type == "MEAL_AREA_PRESENCE":
        return MEAL_CHECKIN_MESSAGE
    return None


def maybe_trigger_proactive_message(event: IoTEvent, asked_event_ids: set[str]) -> str | None:
    if event.event_id in asked_event_ids:
        return None
    message = build_proactive_message(event)
    if message is not None:
        asked_event_ids.add(event.event_id)
    return message
