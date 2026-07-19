from dataclasses import dataclass, field, replace
from datetime import datetime, time, timedelta
from uuid import uuid4

from domain.models import MedicationPlan, MedicationPlanAuditEvent


TIMING_LABELS = {
    "BEFORE_BREAKFAST": "早餐前",
    "AFTER_BREAKFAST": "早餐後",
    "BEFORE_LUNCH": "午餐前",
    "AFTER_LUNCH": "午餐後",
    "BEFORE_DINNER": "晚餐前",
    "AFTER_DINNER": "晚餐後",
    "BEFORE_SLEEP": "睡前",
    "ON_WAKE": "醒來",
    "FIXED_TIME": "固定時間",
}
ALLOWED_TIMINGS = frozenset(TIMING_LABELS)


@dataclass(frozen=True)
class MedicationImageReference:
    image_url: str
    source_name: str
    source_url: str
    reference_id: str
    match_status: str = "MATCHED"


@dataclass(frozen=True)
class OCRMedicationCandidate:
    med_id: str
    name: str
    dose: str
    timing: str
    confidence: float
    frequency: str = ""
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    fixed_times: tuple[str, ...] = ()
    image_reference: MedicationImageReference | None = None
    human_edited: bool = False
    reviewed: bool = False


@dataclass(frozen=True)
class PendingMedicationAudit:
    event_id: str
    med_id: str
    action: str
    actor_id: str
    occurred_at: datetime
    before: dict | None = None
    after: dict | None = None


@dataclass
class PrescriptionOCRResult:
    prescription_id: str
    patient_name: str
    captured_at: datetime
    raw_text: str
    medications: list[OCRMedicationCandidate]
    review_status: str = "NEEDS_REVIEW"
    capture_source: str = "DEMO_SAMPLE"
    audit_events: list[PendingMedicationAudit] = field(default_factory=list)


class OCRValidationError(ValueError):
    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        message = "；".join(f"{field}：{reason}" for field, reason in errors.items())
        super().__init__(message)


TRUSTED_IMAGE_CATALOG = {
    "脈優錠5mg": MedicationImageReference(
        image_url="https://reg.802.mnd.gov.tw/Med/images/drug/ONORV/Apperance1.jpg",
        source_name="國軍高雄總醫院藥品查詢系統",
        source_url=(
            "https://reg.802.mnd.gov.tw/Med/PharmaBooks/Keyword_Detail/"
            "3S4eb5SJISEtvByvl4iTaKqFdrdZzseNBOKBXLdwmJo%3D"
        ),
        reference_id="健保碼 BC21571100",
    )
}


def _normalize_medication_name(name: str) -> str:
    return name.lower().replace(" ", "").replace("５", "5").replace("ｍｇ", "mg")


def lookup_medication_image(name: str) -> MedicationImageReference | None:
    """Return only a trusted, exact-name image match for this deterministic demo."""
    return TRUSTED_IMAGE_CATALOG.get(_normalize_medication_name(name))


def _candidate_snapshot(candidate: OCRMedicationCandidate) -> dict:
    return {
        "name": candidate.name,
        "dose": candidate.dose,
        "frequency": candidate.frequency,
        "timing": candidate.timing,
        "valid_from": candidate.valid_from.isoformat() if candidate.valid_from else None,
        "valid_to": candidate.valid_to.isoformat() if candidate.valid_to else None,
        "fixed_times": list(candidate.fixed_times),
        "confidence": f"{candidate.confidence:.4f}",
        "human_edited": candidate.human_edited,
        "reviewed": candidate.reviewed,
        "image_reference_id": (
            candidate.image_reference.reference_id if candidate.image_reference else None
        ),
    }


def _append_audit(
    result: PrescriptionOCRResult,
    candidate: OCRMedicationCandidate,
    action: str,
    actor_id: str,
    *,
    before: dict | None = None,
    after: dict | None = None,
    occurred_at: datetime | None = None,
) -> None:
    sequence = len(result.audit_events) + 1
    result.audit_events.append(PendingMedicationAudit(
        event_id=f"audit-{result.prescription_id}-{sequence:03d}",
        med_id=candidate.med_id,
        action=action,
        actor_id=actor_id,
        occurred_at=occurred_at or result.captured_at,
        before=before,
        after=after,
    ))


def _refresh_review_status(result: PrescriptionOCRResult) -> None:
    if result.review_status == "CONFIRMED":
        return
    result.review_status = (
        "READY_TO_CONFIRM"
        if result.medications and all(candidate.reviewed for candidate in result.medications)
        else "NEEDS_REVIEW"
    )


def simulate_prescription_ocr(clock, capture_source: str = "DEMO_SAMPLE") -> PrescriptionOCRResult:
    """Return a deterministic candidate set; no image is sent to a real OCR service."""
    candidate = OCRMedicationCandidate(
        med_id="med-001",
        name="脈優錠 5mg",
        dose="1顆",
        timing="AFTER_DINNER",
        confidence=0.96,
        frequency="每日1次",
        valid_from=clock.now,
        valid_to=datetime.combine((clock.now + timedelta(days=30)).date(), time.max),
        image_reference=lookup_medication_image("脈優錠 5mg"),
    )
    result = PrescriptionOCRResult(
        prescription_id=(
            f"rx-demo-{clock.now.strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:8]}"
        ),
        patient_name="王○明",
        captured_at=clock.now,
        raw_text=(
            "王○明\n"
            "脈優錠 5mg\n"
            "每次 1 顆　每日 1 次　晚餐後服用"
        ),
        medications=[candidate],
        capture_source=capture_source,
    )
    _append_audit(
        result,
        candidate,
        "CANDIDATE_CREATED",
        "ocr-simulator",
        after=_candidate_snapshot(candidate),
    )
    return result


def validate_ocr_candidate(candidate: OCRMedicationCandidate) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not candidate.name.strip():
        errors["藥名"] = "必填"
    if not candidate.dose.strip():
        errors["每次劑量"] = "必填"
    if not candidate.frequency.strip():
        errors["頻率"] = "必填"
    if candidate.timing not in ALLOWED_TIMINGS:
        errors["服用時機"] = "服用時機選項不正確"
    if candidate.valid_from is None:
        errors["有效起日"] = "必填"
    if candidate.valid_to is None:
        errors["有效迄日"] = "必填"
    if (
        candidate.valid_from is not None
        and candidate.valid_to is not None
        and candidate.valid_to < candidate.valid_from
    ):
        errors["有效期間"] = "迄日不得早於起日"
    if candidate.timing == "FIXED_TIME":
        if not candidate.fixed_times:
            errors["固定時間"] = "至少必須設定一個具體時間"
        else:
            invalid_times = []
            for fixed_time in candidate.fixed_times:
                try:
                    datetime.strptime(fixed_time, "%H:%M")
                except ValueError:
                    invalid_times.append(fixed_time)
            if invalid_times:
                errors["固定時間"] = "必須使用 HH:MM 格式"
    return errors


def revise_ocr_candidate(
    result: PrescriptionOCRResult,
    med_id: str,
    *,
    name: str,
    dose: str,
    frequency: str,
    timing: str,
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
    fixed_times: tuple[str, ...] | None = None,
    actor_id: str = "family-001",
    occurred_at: datetime | None = None,
) -> OCRMedicationCandidate:
    """Apply a family edit; every edit invalidates the previous item review."""
    if result.review_status == "CONFIRMED":
        raise ValueError("已確認的藥單不可直接修改，請重新建立待確認候選")
    for index, candidate in enumerate(result.medications):
        if candidate.med_id != med_id:
            continue
        before = _candidate_snapshot(candidate)
        revised = replace(
            candidate,
            name=name.strip(),
            dose=dose.strip(),
            frequency=frequency.strip(),
            timing=timing,
            valid_from=valid_from if valid_from is not None else candidate.valid_from,
            valid_to=valid_to if valid_to is not None else candidate.valid_to,
            fixed_times=(
                tuple(fixed_times or ()) if timing == "FIXED_TIME" else ()
            ),
            image_reference=lookup_medication_image(name),
            human_edited=True,
            reviewed=False,
        )
        result.medications[index] = revised
        _append_audit(
            result,
            revised,
            "CANDIDATE_MODIFIED",
            actor_id,
            before=before,
            after=_candidate_snapshot(revised),
            occurred_at=occurred_at,
        )
        _refresh_review_status(result)
        return revised
    raise ValueError(f"Unknown OCR medication candidate: {med_id}")


def add_manual_candidate(
    result: PrescriptionOCRResult,
    *,
    name: str,
    dose: str,
    frequency: str,
    timing: str,
    valid_from: datetime,
    valid_to: datetime,
    fixed_times: tuple[str, ...] = (),
    actor_id: str = "family-001",
    occurred_at: datetime | None = None,
) -> OCRMedicationCandidate:
    if result.review_status == "CONFIRMED":
        raise ValueError("已確認的藥單不可直接新增內容")
    next_number = 1
    existing_ids = {candidate.med_id for candidate in result.medications}
    while f"manual-{next_number:03d}" in existing_ids:
        next_number += 1
    candidate = OCRMedicationCandidate(
        med_id=f"manual-{next_number:03d}",
        name=name.strip(),
        dose=dose.strip(),
        frequency=frequency.strip(),
        timing=timing,
        confidence=0.0,
        valid_from=valid_from,
        valid_to=valid_to,
        fixed_times=tuple(fixed_times) if timing == "FIXED_TIME" else (),
        image_reference=lookup_medication_image(name),
        human_edited=True,
    )
    result.medications.append(candidate)
    _append_audit(
        result,
        candidate,
        "CANDIDATE_ADDED_MANUALLY",
        actor_id,
        after=_candidate_snapshot(candidate),
        occurred_at=occurred_at,
    )
    _refresh_review_status(result)
    return candidate


def delete_ocr_candidate(
    result: PrescriptionOCRResult,
    med_id: str,
    actor_id: str = "family-001",
    occurred_at: datetime | None = None,
) -> None:
    if result.review_status == "CONFIRMED":
        raise ValueError("已確認的藥單不可直接刪除內容")
    for index, candidate in enumerate(result.medications):
        if candidate.med_id != med_id:
            continue
        result.medications.pop(index)
        _append_audit(
            result,
            candidate,
            "CANDIDATE_DELETED",
            actor_id,
            before=_candidate_snapshot(candidate),
            occurred_at=occurred_at,
        )
        _refresh_review_status(result)
        return
    raise ValueError(f"Unknown OCR medication candidate: {med_id}")


def review_ocr_candidate(
    result: PrescriptionOCRResult,
    med_id: str,
    actor_id: str = "family-001",
    occurred_at: datetime | None = None,
) -> OCRMedicationCandidate:
    if result.review_status == "CONFIRMED":
        raise ValueError("此藥單已確認")
    for index, candidate in enumerate(result.medications):
        if candidate.med_id != med_id:
            continue
        errors = validate_ocr_candidate(candidate)
        if errors:
            raise OCRValidationError(errors)
        reviewed = replace(candidate, reviewed=True)
        result.medications[index] = reviewed
        _append_audit(
            result,
            reviewed,
            "CANDIDATE_REVIEWED",
            actor_id,
            before=_candidate_snapshot(candidate),
            after=_candidate_snapshot(reviewed),
            occurred_at=occurred_at,
        )
        _refresh_review_status(result)
        return reviewed
    raise ValueError(f"Unknown OCR medication candidate: {med_id}")


def _plan_snapshot(plan: MedicationPlan) -> dict:
    return {
        "name": plan.name,
        "dose": plan.dose,
        "frequency": plan.frequency,
        "timing": plan.timing,
        "valid_from": plan.valid_from.isoformat(),
        "valid_to": plan.valid_to.isoformat() if plan.valid_to else None,
        "fixed_times": list(plan.fixed_times),
        "confirmed": plan.confirmed,
        "active": plan.active,
    }


def persist_ocr_audit_events(repo, result: PrescriptionOCRResult, user_id: str) -> None:
    """Persist pending candidate history; repeated calls are idempotent by event ID."""
    for pending in result.audit_events:
        repo.put_medication_audit_event(MedicationPlanAuditEvent(
            event_id=pending.event_id,
            user_id=user_id,
            med_id=pending.med_id,
            action=pending.action,
            actor_id=pending.actor_id,
            occurred_at=pending.occurred_at,
            before=pending.before,
            after=pending.after,
        ))


def confirm_ocr_result(
    repo,
    result: PrescriptionOCRResult,
    user_id: str,
    confirmed_by: str = "family-001",
    created_by: str | None = None,
    confirmed_at: datetime | None = None,
) -> list[MedicationPlan]:
    """Validate, persist and activate only individually reviewed candidates."""
    if result.review_status == "CONFIRMED":
        existing = {plan.med_id: plan for plan in repo.get_medication_plans(user_id)}
        return [existing[candidate.med_id] for candidate in result.medications if candidate.med_id in existing]
    if not result.medications:
        raise OCRValidationError({"藥物資料": "至少需要一筆候選資料"})

    errors: dict[str, str] = {}
    for candidate in result.medications:
        for field_name, reason in validate_ocr_candidate(candidate).items():
            errors[f"{candidate.med_id}.{field_name}"] = reason
        if not candidate.reviewed:
            errors[f"{candidate.med_id}.人工確認"] = "必須逐筆核對"
    if errors:
        raise OCRValidationError(errors)

    actor = created_by or confirmed_by
    confirmation_time = confirmed_at or result.captured_at
    plans = []
    persist_ocr_audit_events(repo, result, user_id)

    for index, candidate in enumerate(result.medications, start=1):
        plan = MedicationPlan(
            med_id=candidate.med_id,
            user_id=user_id,
            name=candidate.name,
            dose=candidate.dose,
            timing=candidate.timing,
            valid_from=candidate.valid_from,
            valid_to=candidate.valid_to,
            confirmed=True,
            created_by=actor,
            updated_at=confirmation_time,
            frequency=candidate.frequency,
            fixed_times=candidate.fixed_times,
            active=True,
            created_at=result.captured_at,
            confirmed_by=confirmed_by,
            confirmed_at=confirmation_time,
        )
        repo.seed_medication_plan(plan)
        snapshot = _plan_snapshot(plan)
        repo.put_medication_audit_event(MedicationPlanAuditEvent(
            event_id=f"audit-{result.prescription_id}-confirmed-{index:03d}",
            user_id=user_id,
            med_id=plan.med_id,
            action="PLAN_CONFIRMED_AND_ACTIVATED",
            actor_id=confirmed_by,
            occurred_at=confirmation_time,
            after=snapshot,
        ))
        plans.append(plan)
    result.review_status = "CONFIRMED"
    return plans


def format_ocr_result(result: PrescriptionOCRResult) -> str:
    lines = []
    for candidate in result.medications:
        timing = TIMING_LABELS.get(candidate.timing, candidate.timing)
        if candidate.timing == "FIXED_TIME" and candidate.fixed_times:
            timing = f"{timing}（{', '.join(candidate.fixed_times)}）"
        valid_period = (
            f"{candidate.valid_from:%Y-%m-%d}～{candidate.valid_to:%Y-%m-%d}"
            if candidate.valid_from and candidate.valid_to
            else "未完整設定"
        )
        lines.append(
            f"- **{candidate.name}**｜每次 {candidate.dose}｜"
            f"{candidate.frequency}｜{timing}｜有效期間 {valid_period}｜"
            f"辨識信心 {candidate.confidence:.0%}"
        )
    return "\n".join(lines)
