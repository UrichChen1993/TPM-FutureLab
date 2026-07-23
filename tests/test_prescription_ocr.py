from datetime import datetime, timedelta

import pytest

from simulator.clock import SimClock
from simulator.prescription_ocr import (
    OCRMedicationCandidate,
    OCRValidationError,
    add_manual_candidate,
    confirm_ocr_result,
    delete_ocr_candidate,
    lookup_medication_image,
    persist_ocr_audit_events,
    review_ocr_candidate,
    revise_ocr_candidate,
    simulate_prescription_ocr,
    validate_ocr_candidate,
)
from storage.memory_backend import InMemoryRepository


def test_simulated_ocr_result_requires_human_review():
    clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))

    result = simulate_prescription_ocr(clock)

    assert result.review_status == "NEEDS_REVIEW"
    assert result.medications[0].name == "脈優錠 5mg"
    assert result.medications[0].confidence == 0.96
    assert result.medications[0].frequency == "每日1次"
    assert result.medications[0].valid_to == datetime(2026, 8, 16, 23, 59, 59, 999999)
    assert result.medications[0].reviewed is False
    assert result.medications[0].image_reference is not None


def test_trusted_image_lookup_requires_an_exact_normalized_name():
    matched = lookup_medication_image("脈優錠 ５ｍｇ")

    assert matched is not None
    assert matched.reference_id == "健保碼 BC21571100"
    assert lookup_medication_image("外觀相似的白色藥錠") is None


def test_family_can_revise_ocr_candidate_before_confirmation():
    clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))
    result = simulate_prescription_ocr(clock, capture_source="CAMERA")

    revised = revise_ocr_candidate(
        result,
        "med-001",
        name="家屬核對後的藥名",
        dose="半顆",
        frequency="每日2次",
        timing="BEFORE_DINNER",
    )

    assert result.capture_source == "CAMERA"
    assert revised.human_edited is True
    assert revised.image_reference is None
    assert revised.dose == "半顆"
    assert revised.reviewed is False
    assert result.review_status == "NEEDS_REVIEW"


def test_confirmation_is_blocked_until_every_candidate_is_reviewed():
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))
    result = simulate_prescription_ocr(clock)

    with pytest.raises(OCRValidationError) as exc_info:
        confirm_ocr_result(repo, result, "user-001")

    assert "med-001.人工確認" in exc_info.value.errors
    assert repo.get_medication_plans("user-001") == []


def test_fixed_time_candidate_requires_concrete_hh_mm_time():
    candidate = OCRMedicationCandidate(
        med_id="med-fixed", name="測試藥", dose="1顆", frequency="每日1次",
        timing="FIXED_TIME", confidence=0.8,
        valid_from=datetime(2026, 7, 17), valid_to=datetime(2026, 7, 31),
    )

    assert validate_ocr_candidate(candidate)["固定時間"] == "至少必須設定一個具體時間"
    assert validate_ocr_candidate(
        OCRMedicationCandidate(**{**candidate.__dict__, "fixed_times": ("08:00",)})
    ) == {}


def test_family_can_add_and_delete_manual_candidate():
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))
    result = simulate_prescription_ocr(clock)
    manual = add_manual_candidate(
        result,
        name="手動輸入藥物",
        dose="1顆",
        frequency="每日1次",
        timing="FIXED_TIME",
        valid_from=clock.now,
        valid_to=clock.now + timedelta(days=7),
        fixed_times=("08:00",),
    )

    assert manual.human_edited is True
    assert len(result.medications) == 2

    delete_ocr_candidate(result, manual.med_id)
    persist_ocr_audit_events(repo, result, "user-001")

    assert [candidate.med_id for candidate in result.medications] == ["med-001"]
    assert result.audit_events[-1].action == "CANDIDATE_DELETED"
    assert [
        event.action for event in repo.list_medication_audit_events("user-001", manual.med_id)
    ] == ["CANDIDATE_ADDED_MANUALLY", "CANDIDATE_DELETED"]


def test_confirmed_ocr_result_becomes_active_medication_plan():
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))
    result = simulate_prescription_ocr(clock)
    review_ocr_candidate(result, "med-001")

    confirmed_at = datetime(2026, 7, 17, 17, 35)
    plans = confirm_ocr_result(repo, result, "user-001", confirmed_at=confirmed_at)

    assert result.review_status == "CONFIRMED"
    assert plans[0].confirmed is True
    assert plans[0].created_by == "family-001"
    assert plans[0].confirmed_by == "family-001"
    assert plans[0].created_at == result.captured_at
    assert plans[0].confirmed_at == confirmed_at
    assert plans[0].active is True
    assert plans[0].frequency == "每日1次"
    assert repo.get_medication_plans("user-001") == plans
    actions = [event.action for event in repo.list_medication_audit_events("user-001")]
    assert actions == [
        "CANDIDATE_CREATED",
        "CANDIDATE_REVIEWED",
        "PLAN_CONFIRMED_AND_ACTIVATED",
    ]


def test_confirming_same_scan_twice_does_not_duplicate_plan():
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))
    result = simulate_prescription_ocr(clock)
    review_ocr_candidate(result, "med-001")

    confirm_ocr_result(repo, result, "user-001")
    confirm_ocr_result(repo, result, "user-001")

    assert len(repo.get_medication_plans("user-001")) == 1
    assert len(repo.list_medication_audit_events("user-001")) == 3


def test_separate_scans_keep_distinct_append_only_audit_events():
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))
    first = simulate_prescription_ocr(clock)
    second = simulate_prescription_ocr(clock)

    review_ocr_candidate(first, "med-001")
    confirm_ocr_result(repo, first, "user-001")
    review_ocr_candidate(second, "med-001")
    confirm_ocr_result(repo, second, "user-001")

    events = repo.list_medication_audit_events("user-001")
    assert len(events) == 6
    assert len({event.event_id for event in events}) == 6
