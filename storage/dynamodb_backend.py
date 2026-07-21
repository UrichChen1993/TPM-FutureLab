from datetime import datetime

import boto3

from domain.models import (
    DoseRecord,
    IoTEvent,
    MedicationPlan,
    MedicationPlanAuditEvent,
    Notification,
    VitalReading,
)
from domain.states import DoseStatus
from storage.base import Repository


class DynamoDBRepository(Repository):
    def __init__(self, table_name: str, region: str):
        self._table = boto3.resource("dynamodb", region_name=region).Table(table_name)
        # Fail during repository creation instead of silently serving a healthy UI
        # with a missing table or an invalid App Runner instance role.
        self._table.load()

    @staticmethod
    def _pk(user_id: str) -> str:
        return f"USER#{user_id}"

    def _query_all(self, **kwargs) -> list[dict]:
        """Read every query page so older records are not silently omitted."""
        items = []
        while True:
            response = self._table.query(**kwargs)
            items.extend(response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                return items
            kwargs["ExclusiveStartKey"] = last_key

    def get_medication_plans(self, user_id: str) -> list[MedicationPlan]:
        items = self._query_all(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
            ExpressionAttributeValues={":pk": self._pk(user_id), ":prefix": "MEDICATION#"},
            ConsistentRead=True,
        )
        return [
            MedicationPlan(
                med_id=item["med_id"], user_id=user_id, name=item["name"], dose=item["dose"],
                timing=item["timing"], valid_from=datetime.fromisoformat(item["valid_from"]),
                valid_to=datetime.fromisoformat(item["valid_to"]) if item.get("valid_to") else None,
                confirmed=item["confirmed"], created_by=item["created_by"],
                updated_at=datetime.fromisoformat(item["updated_at"]),
                frequency=item.get("frequency", ""),
                fixed_times=tuple(item.get("fixed_times", [])),
                active=item.get("active", True),
                created_at=(
                    datetime.fromisoformat(item["created_at"])
                    if item.get("created_at") else None
                ),
                confirmed_by=item.get("confirmed_by"),
                confirmed_at=(
                    datetime.fromisoformat(item["confirmed_at"])
                    if item.get("confirmed_at") else None
                ),
            )
            for item in items
        ]

    def seed_medication_plan(self, plan: MedicationPlan) -> None:
        self._table.put_item(Item={
            "PK": self._pk(plan.user_id), "SK": f"MEDICATION#{plan.med_id}",
            "med_id": plan.med_id, "name": plan.name, "dose": plan.dose, "timing": plan.timing,
            "valid_from": plan.valid_from.isoformat(),
            "valid_to": plan.valid_to.isoformat() if plan.valid_to else None,
            "confirmed": plan.confirmed, "created_by": plan.created_by,
            "updated_at": plan.updated_at.isoformat(),
            "frequency": plan.frequency,
            "fixed_times": list(plan.fixed_times),
            "active": plan.active,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "confirmed_by": plan.confirmed_by,
            "confirmed_at": plan.confirmed_at.isoformat() if plan.confirmed_at else None,
        })

    def put_medication_audit_event(self, event: MedicationPlanAuditEvent) -> None:
        self._table.put_item(Item={
            "PK": self._pk(event.user_id),
            "SK": f"MEDICATION_AUDIT#{event.occurred_at.isoformat()}#{event.event_id}",
            "event_id": event.event_id,
            "med_id": event.med_id,
            "action": event.action,
            "actor_id": event.actor_id,
            "before": event.before,
            "after": event.after,
        })

    def list_medication_audit_events(
        self, user_id: str, med_id: str | None = None
    ) -> list[MedicationPlanAuditEvent]:
        items = self._query_all(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
            ExpressionAttributeValues={
                ":pk": self._pk(user_id),
                ":prefix": "MEDICATION_AUDIT#",
            },
            ConsistentRead=True,
        )
        events = []
        for item in items:
            if med_id is not None and item["med_id"] != med_id:
                continue
            _, occurred_at, _ = item["SK"].split("#", 2)
            events.append(MedicationPlanAuditEvent(
                event_id=item["event_id"],
                user_id=user_id,
                med_id=item["med_id"],
                action=item["action"],
                actor_id=item["actor_id"],
                occurred_at=datetime.fromisoformat(occurred_at),
                before=item.get("before"),
                after=item.get("after"),
            ))
        return events

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
            ScanIndexForward=False, Limit=1, ConsistentRead=True,
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
        resp = self._table.get_item(
            Key={"PK": self._pk(user_id), "SK": f"DOSE#{date}#{med_id}#{slot}"},
            ConsistentRead=True,
        )
        item = resp.get("Item")
        if item is None:
            return None
        return self._item_to_dose(item, user_id, date, med_id, slot)

    def list_dose_records(self, user_id: str, date: str) -> list[DoseRecord]:
        items = self._query_all(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
            ExpressionAttributeValues={":pk": self._pk(user_id), ":prefix": f"DOSE#{date}#"},
            ConsistentRead=True,
        )
        records = []
        for item in items:
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
        items = self._query_all(
            KeyConditionExpression="PK = :pk AND begins_with(SK, :prefix)",
            ExpressionAttributeValues={":pk": self._pk(user_id), ":prefix": "NOTIFICATION#"},
            ConsistentRead=True,
        )
        results = []
        for item in items:
            occurred_at = item["SK"].split("#")[1]
            results.append(Notification(
                user_id=user_id, notification_id=item["notification_id"],
                occurred_at=datetime.fromisoformat(occurred_at), reason=item["reason"],
                severity=item["severity"], message=item["message"],
            ))
        return results
