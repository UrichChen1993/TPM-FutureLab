from dataclasses import dataclass
from datetime import datetime, time

from domain.models import DoseRecord, Notification
from domain.states import DoseStatus, NotificationSeverity
from rules.config import (
    EMERGENCY_UNRESPONSIVE_MINUTES,
    FIRST_REMINDER_DELAY_MINUTES,
    MISSED_THRESHOLD_MINUTES,
    SECOND_REMINDER_DELAY_MINUTES,
)

SLOT_TIMES = {"BREAKFAST": time(8, 0), "LUNCH": time(12, 0), "DINNER": time(18, 0)}

_DONE_STATUSES = (DoseStatus.SELF_REPORTED, DoseStatus.SENSOR_SUPPORTED)


@dataclass
class EscalationResult:
    new_status: DoseStatus
    send_reminder: bool = False
    notify_severity: str | None = None


def evaluate_dose(record: DoseRecord, now: datetime) -> EscalationResult:
    if record.status in _DONE_STATUSES:
        return EscalationResult(new_status=record.status)

    minutes_since_due = (now - record.due_at).total_seconds() / 60

    if minutes_since_due < 0:
        return EscalationResult(new_status=DoseStatus.SCHEDULED)

    if record.status == DoseStatus.MISSED:
        if minutes_since_due >= EMERGENCY_UNRESPONSIVE_MINUTES:
            return EscalationResult(new_status=DoseStatus.MISSED, notify_severity=NotificationSeverity.HIGH.value)
        return EscalationResult(new_status=DoseStatus.MISSED)

    if minutes_since_due >= MISSED_THRESHOLD_MINUTES:
        return EscalationResult(new_status=DoseStatus.MISSED, notify_severity=NotificationSeverity.MEDIUM.value)

    if minutes_since_due >= FIRST_REMINDER_DELAY_MINUTES:
        due_for_second_reminder = (
            record.status == DoseStatus.REMINDED
            and record.reminded_at is not None
            and (now - record.reminded_at).total_seconds() / 60 >= SECOND_REMINDER_DELAY_MINUTES
        )
        if record.status == DoseStatus.DUE or due_for_second_reminder:
            return EscalationResult(new_status=DoseStatus.REMINDED, send_reminder=True)
        return EscalationResult(new_status=record.status)

    return EscalationResult(new_status=DoseStatus.DUE)


def apply_escalation(repo, record: DoseRecord, now: datetime) -> EscalationResult:
    result = evaluate_dose(record, now)
    record.status = result.new_status
    if result.send_reminder:
        record.reminded_at = now
    repo.put_dose_record(record)

    if result.notify_severity:
        reason = f"dose_{record.med_id}_{record.slot}_{result.new_status.value}_{result.notify_severity}"
        already_notified = any(n.reason == reason for n in repo.list_notifications(record.user_id))
        if not already_notified:
            repo.put_notification(Notification(
                user_id=record.user_id,
                notification_id=f"notif-{record.user_id}-{reason}",
                occurred_at=now,
                reason=reason,
                severity=result.notify_severity,
                message=f"{record.med_id} {record.slot} 服藥狀態：{result.new_status.value}",
            ))

    return result


def ensure_today_doses(repo, clock, user_id: str) -> None:
    """MVP scope: only AFTER_MEAL plans map to the DINNER slot.

    ponytail: BEFORE_MEAL/FIXED_TIME mapping isn't demoed yet; extend
    SLOT_TIMES/this function when those timings are actually needed.
    """
    today = clock.now.strftime("%Y-%m-%d")
    for plan in repo.get_medication_plans(user_id):
        if not plan.confirmed or plan.timing != "AFTER_MEAL":
            continue
        slot = "DINNER"
        if repo.get_dose_record(user_id, today, plan.med_id, slot) is not None:
            continue
        due_at = datetime.combine(clock.now.date(), SLOT_TIMES[slot])
        repo.put_dose_record(DoseRecord(
            user_id=user_id, date=today, med_id=plan.med_id, slot=slot,
            status=DoseStatus.SCHEDULED, due_at=due_at,
        ))
