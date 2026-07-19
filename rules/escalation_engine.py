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

SLOT_TIMES = {
    "BREAKFAST": time(8, 0),
    "LUNCH": time(12, 0),
    "DINNER": time(18, 0),
    "ON_WAKE": time(7, 0),
    "BEFORE_SLEEP": time(22, 0),
}

# Every meal-relative timing shares its meal's slot/due time; "before" vs "after"
# only changes the wording used when talking to the user.
TIMING_SLOTS = {
    "BEFORE_BREAKFAST": "BREAKFAST", "AFTER_BREAKFAST": "BREAKFAST",
    "BEFORE_LUNCH": "LUNCH", "AFTER_LUNCH": "LUNCH",
    "BEFORE_DINNER": "DINNER", "AFTER_DINNER": "DINNER",
    "BEFORE_SLEEP": "BEFORE_SLEEP",
    "ON_WAKE": "ON_WAKE",
}

_DONE_STATUSES = (DoseStatus.SELF_REPORTED, DoseStatus.SENSOR_SUPPORTED)

_ESCALATION_MESSAGES = {
    NotificationSeverity.MEDIUM.value: "逾時未服藥（第1次提醒後未回應）",
    NotificationSeverity.HIGH.value: "逾時未服藥（第2次提醒後仍未回應，已升級通知）",
}


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
        reason = f"dose_{record.date}_{record.med_id}_{record.slot}_{result.new_status.value}_{result.notify_severity}"
        already_notified = any(n.reason == reason for n in repo.list_notifications(record.user_id))
        if not already_notified:
            repo.put_notification(Notification(
                user_id=record.user_id,
                notification_id=f"notif-{record.user_id}-{reason}",
                occurred_at=now,
                reason=reason,
                severity=result.notify_severity,
                message=f"{record.med_id} {record.slot} {_ESCALATION_MESSAGES[result.notify_severity]}",
            ))

    return result


def ensure_today_doses(repo, clock, user_id: str) -> None:
    """Create today's records for active plans, one per meal/sleep/wake slot or fixed time."""
    today = clock.now.strftime("%Y-%m-%d")
    for plan in repo.get_medication_plans(user_id):
        if not plan.is_active_at(clock.now):
            continue
        schedules: list[tuple[str, time]] = []
        slot = TIMING_SLOTS.get(plan.timing)
        if slot is not None:
            schedules.append((slot, SLOT_TIMES[slot]))
        elif plan.timing == "FIXED_TIME":
            for fixed_time in plan.fixed_times:
                try:
                    parsed_time = datetime.strptime(fixed_time, "%H:%M").time()
                except ValueError:
                    continue
                schedules.append((f"FIXED_{fixed_time.replace(':', '')}", parsed_time))

        for slot, due_time in schedules:
            if repo.get_dose_record(user_id, today, plan.med_id, slot) is not None:
                continue
            due_at = datetime.combine(clock.now.date(), due_time)
            repo.put_dose_record(DoseRecord(
                user_id=user_id, date=today, med_id=plan.med_id, slot=slot,
                status=DoseStatus.SCHEDULED, due_at=due_at,
            ))
