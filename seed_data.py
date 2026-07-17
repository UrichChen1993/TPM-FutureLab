from datetime import datetime

from domain.models import MedicationPlan
from storage.base import Repository
from storage.factory import get_repository


def seed_demo_user(repo: Repository | None = None, user_id: str = "user-001") -> None:
    repo = repo or get_repository()
    now = datetime(2026, 7, 17, 8, 0)
    repo.seed_medication_plan(MedicationPlan(
        med_id="med-001", user_id=user_id, name="脈康錠 5mg", dose="1顆",
        timing="AFTER_MEAL", valid_from=now, valid_to=None,
        confirmed=True, created_by="family-001", updated_at=now,
    ))


if __name__ == "__main__":
    seed_demo_user()
