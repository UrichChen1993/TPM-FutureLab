from seed_data import seed_demo_user
from storage.memory_backend import InMemoryRepository


def test_seed_demo_user_creates_confirmed_plan():
    repo = InMemoryRepository()
    seed_demo_user(repo, "user-001")
    plans = repo.get_medication_plans("user-001")
    assert len(plans) == 1
    assert plans[0].confirmed is True
    assert plans[0].timing == "AFTER_DINNER"
    assert plans[0].name == "脈優錠 5mg"
    assert plans[0].frequency == "每日1次"
    assert plans[0].confirmed_by == "family-001"
    assert len(repo.list_medication_audit_events("user-001")) == 1
