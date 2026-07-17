from datetime import datetime

import boto3

from domain.models import DoseRecord, IoTEvent, MedicationPlan, Notification, VitalReading
from domain.states import DoseStatus
from storage.base import Repository


class DynamoDBRepository(Repository):
    def __init__(self, table_name: str, region: str):
        self._table = boto3.resource("dynamodb", region_name=region).Table(table_name)

    @staticmethod
    def _pk(user_id: str) -> str:
        return f"USER#{user_id}"

    def get_medication_plans(self, user_id: str) -> list[MedicationPlan]:
        resp = self._table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
            ExpressionAttributeValues={":pk": self._pk(user_id), ":prefix": "MEDICATION#"},
        )
        return [
            MedicationPlan(
                med_id=item["med_id"], user_id=user_id, name=item["name"], dose=item["dose"],
                timing=item["timing"], valid_from=datetime.fromisoformat(item["valid_from"]),
                valid_to=datetime.fromisoformat(item["valid_to"]) if item.get("valid_to") else None,
                confirmed=item["confirmed"], created_by=item["created_by"],
                updated_at=datetime.fromisoformat(item["updated_at"]),
            )
            for item in resp.get("Items", [])
        ]

    def seed_medication_plan(self, plan: MedicationPlan) -> None:
        self._table.put_item(Item={
            "PK": self._pk(plan.user_id), "SK": f"MEDICATION#{plan.med_id}",
            "med_id": plan.med_id, "name": plan.name, "dose": plan.dose, "timing": plan.timing,
            "valid_from": plan.valid_from.isoformat(),
            "valid_to": plan.valid_to.isoformat() if plan.valid_to else None,
            "confirmed": plan.confirmed, "created_by": plan.created_by,
            "updated_at": plan.updated_at.isoformat(),
        })

    def put_vital(self, vital: VitalReading) -> None:
        self._table.put_item(Item={
            "PK": self._pk(vital.user_id), "SK": f"VITAL#{vital.measured_at.isoformat()}",
            "systolic": vital.systolic, "diastolic": vital.diastolic,
            "heart_rate": vital.heart_rate, "source": vital.source,
        })

    def get_latest_vital(self, user_id: str) -> VitalReading | None:
        resp = self._table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
            ExpressionAttributeValues={":pk": self._pk(user_id), ":prefix": "VITAL#"},
            ScanIndexForward=False, Limit=1,
        )
        items = resp.get("Items", [])
        if not items:
            return None
        item = items[0]
        return VitalReading(
            user_id=user_id, systolic=int(item["systolic"]), diastolic=int(item["diastolic"]),
            heart_rate=int(item["heart_rate"]),
            measured_at=datetime.fromisoformat(item["SK"].split("#", 1)[1]), source=item["source"],
        )

    def put_iot_event(self, event: IoTEvent) -> None:
        self._table.put_item(Item={
            "PK": self._pk(event.user_id),
            "SK": f"IOT_EVENT#{event.occurred_at.isoformat()}#{event.event_id}",
            "event_id": event.event_id, "event_type": event.event_type, "payload": event.payload,
        })

    def put_dose_record(self, record: DoseRecord) -> None:
        self._table.put_item(Item={
            "PK": self._pk(record.user_id), "SK": f"DOSE#{record.date}#{record.med_id}#{record.slot}",
            "status": record.status.value, "due_at": record.due_at.isoformat(),
            "reminded_at": record.reminded_at.isoformat() if record.reminded_at else None,
            "completed_at": record.completed_at.isoformat() if record.completed_at else None,
            "source": record.source, "confidence": record.confidence,
        })

    def get_dose_record(self, user_id: str, date: str, med_id: str, slot: str) -> DoseRecord | None:
        resp = self._table.get_item(Key={"PK": self._pk(user_id), "SK": f"DOSE#{date}#{med_id}#{slot}"})
        item = resp.get("Item")
        if item is None:
            return None
        return self._item_to_dose(item, user_id, date, med_id, slot)

    def list_dose_records(self, user_id: str, date: str) -> list[DoseRecord]:
        resp = self._table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
            ExpressionAttributeValues={":pk": self._pk(user_id), ":prefix": f"DOSE#{date}#"},
        )
        records = []
        for item in resp.get("Items", []):
            _, _, med_id, slot = item["SK"].split("#")
            records.append(self._item_to_dose(item, user_id, date, med_id, slot))
        return records

    @staticmethod
    def _item_to_dose(item: dict, user_id: str, date: str, med_id: str, slot: str) -> DoseRecord:
        return DoseRecord(
            user_id=user_id, date=date, med_id=med_id, slot=slot,
            status=DoseStatus(item["status"]), due_at=datetime.fromisoformat(item["due_at"]),
            reminded_at=datetime.fromisoformat(item["reminded_at"]) if item.get("reminded_at") else None,
            completed_at=datetime.fromisoformat(item["completed_at"]) if item.get("completed_at") else None,
            source=item.get("source"), confidence=item.get("confidence"),
        )

    def put_notification(self, notification: Notification) -> None:
        self._table.put_item(Item={
            "PK": self._pk(notification.user_id),
            "SK": f"NOTIFICATION#{notification.occurred_at.isoformat()}#{notification.notification_id}",
            "notification_id": notification.notification_id, "reason": notification.reason,
            "severity": notification.severity, "message": notification.message,
        })

    def list_notifications(self, user_id: str) -> list[Notification]:
        resp = self._table.query(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
            ExpressionAttributeValues={":pk": self._pk(user_id), ":prefix": "NOTIFICATION#"},
        )
        results = []
        for item in resp.get("Items", []):
            occurred_at = item["SK"].split("#")[1]
            results.append(Notification(
                user_id=user_id, notification_id=item["notification_id"],
                occurred_at=datetime.fromisoformat(occurred_at), reason=item["reason"],
                severity=item["severity"], message=item["message"],
            ))
        return results
