from datetime import datetime

from domain.models import MedicationPlan, MedicationPlanAuditEvent
from storage.base import Repository
from storage.factory import get_repository


def seed_demo_user(repo: Repository | None = None, user_id: str = "user-001") -> None:
    repo = repo or get_repository()
    now = datetime(2026, 7, 17, 8, 0)
    plan = MedicationPlan(
        med_id="med-001", user_id=user_id, name="脈優錠 5mg", dose="1顆",
        timing="AFTER_DINNER", valid_from=now, valid_to=None,
        confirmed=True, created_by="family-001", updated_at=now, frequency="每日1次",
        active=True, created_at=now, confirmed_by="family-001", confirmed_at=now,
    )
    repo.seed_medication_plan(plan)
    repo.put_medication_audit_event(MedicationPlanAuditEvent(
        event_id=f"audit-demo-seed-{user_id}-med-001",
        user_id=user_id,
        med_id=plan.med_id,
        action="DEMO_PLAN_SEEDED_AND_ACTIVATED",
        actor_id="family-001",
        occurred_at=now,
        after={
            "name": plan.name,
            "dose": plan.dose,
            "frequency": plan.frequency,
            "timing": plan.timing,
            "confirmed": plan.confirmed,
            "active": plan.active,
        },
    ))


if __name__ == "__main__":
    seed_demo_user()
