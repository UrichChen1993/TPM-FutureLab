from abc import ABC, abstractmethod

from domain.models import (
    DoseRecord,
    IoTEvent,
    MedicationPlan,
    MedicationPlanAuditEvent,
    Notification,
    VitalReading,
)


class Repository(ABC):
    @abstractmethod
    def get_medication_plans(self, user_id: str) -> list[MedicationPlan]: ...

    @abstractmethod
    def seed_medication_plan(self, plan: MedicationPlan) -> None: ...

    @abstractmethod
    def put_medication_audit_event(self, event: MedicationPlanAuditEvent) -> None: ...

    @abstractmethod
    def list_medication_audit_events(
        self, user_id: str, med_id: str | None = None
    ) -> list[MedicationPlanAuditEvent]: ...

    @abstractmethod
    def put_vital(self, vital: VitalReading) -> None: ...

    @abstractmethod
    def get_latest_vital(self, user_id: str) -> VitalReading | None: ...

    @abstractmethod
    def put_iot_event(self, event: IoTEvent) -> None: ...

    @abstractmethod
    def put_dose_record(self, record: DoseRecord) -> None: ...

    @abstractmethod
    def get_dose_record(self, user_id: str, date: str, med_id: str, slot: str) -> DoseRecord | None: ...

    @abstractmethod
    def list_dose_records(self, user_id: str, date: str) -> list[DoseRecord]: ...

    @abstractmethod
    def put_notification(self, notification: Notification) -> None: ...

    @abstractmethod
    def list_notifications(self, user_id: str) -> list[Notification]: ...
