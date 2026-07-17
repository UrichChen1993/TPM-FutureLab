from domain.models import DoseRecord, IoTEvent, MedicationPlan, Notification, VitalReading
from storage.base import Repository


class InMemoryRepository(Repository):
    def __init__(self):
        self._plans: dict[str, list[MedicationPlan]] = {}
        self._vitals: dict[str, list[VitalReading]] = {}
        self._iot_events: dict[str, list[IoTEvent]] = {}
        self._doses: dict[tuple[str, str, str, str], DoseRecord] = {}
        self._notifications: dict[str, list[Notification]] = {}

    def seed_medication_plan(self, plan: MedicationPlan) -> None:
        self._plans.setdefault(plan.user_id, []).append(plan)

    def get_medication_plans(self, user_id: str) -> list[MedicationPlan]:
        return list(self._plans.get(user_id, []))

    def put_vital(self, vital: VitalReading) -> None:
        self._vitals.setdefault(vital.user_id, []).append(vital)

    def get_latest_vital(self, user_id: str) -> VitalReading | None:
        readings = self._vitals.get(user_id, [])
        if not readings:
            return None
        return max(readings, key=lambda v: v.measured_at)

    def put_iot_event(self, event: IoTEvent) -> None:
        self._iot_events.setdefault(event.user_id, []).append(event)

    def put_dose_record(self, record: DoseRecord) -> None:
        self._doses[(record.user_id, record.date, record.med_id, record.slot)] = record

    def get_dose_record(self, user_id: str, date: str, med_id: str, slot: str) -> DoseRecord | None:
        return self._doses.get((user_id, date, med_id, slot))

    def list_dose_records(self, user_id: str, date: str) -> list[DoseRecord]:
        return [
            record for (uid, d, _, _), record in self._doses.items()
            if uid == user_id and d == date
        ]

    def put_notification(self, notification: Notification) -> None:
        self._notifications.setdefault(notification.user_id, []).append(notification)

    def list_notifications(self, user_id: str) -> list[Notification]:
        return list(self._notifications.get(user_id, []))
