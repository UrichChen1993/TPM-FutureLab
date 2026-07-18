from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from domain.states import DoseStatus
from rules.risk_engine import classify_vitals, combine_risk


class RecordDoseArgs(BaseModel):
    med_id: str = Field(description="要記錄的藥物 ID")
    slot: str = Field(description="服藥時段，例如 DINNER")


class GetCurrentVitalsArgs(BaseModel):
    danger_symptom_confirmed: bool = Field(
        default=False, description="使用者是否已確認有胸痛、呼吸困難等危險警訊"
    )


def build_tools(repo, clock, user_id: str) -> list[StructuredTool]:
    def get_current_vitals(danger_symptom_confirmed: bool = False) -> dict:
        vital = repo.get_latest_vital(user_id)
        if vital is None:
            return {"available": False, "reason": "no_data"}
        risk = classify_vitals(vital.systolic, vital.diastolic, vital.heart_rate, vital.measured_at, clock.now)
        final_risk = combine_risk(risk, danger_symptom_confirmed)
        return {
            "available": risk.value != "unknown",
            "systolic": vital.systolic,
            "diastolic": vital.diastolic,
            "heart_rate": vital.heart_rate,
            "measured_at": vital.measured_at.isoformat(),
            "source": vital.source,
            "risk_level": final_risk.value,
        }

    def get_medication_plan() -> list[dict]:
        return [
            {"med_id": p.med_id, "name": p.name, "dose": p.dose, "timing": p.timing}
            for p in repo.get_medication_plans(user_id) if p.confirmed
        ]

    def record_dose_self_report(med_id: str, slot: str) -> dict:
        today = clock.now.strftime("%Y-%m-%d")
        record = repo.get_dose_record(user_id, today, med_id, slot)
        if record is None:
            return {"ok": False, "reason": "dose_not_scheduled"}
        record.status = DoseStatus.SELF_REPORTED
        record.completed_at = clock.now
        record.source = "voice"
        record.confidence = "self_reported"
        repo.put_dose_record(record)
        return {"ok": True, "status": record.status.value}

    def get_dose_history() -> list[dict]:
        today = clock.now.strftime("%Y-%m-%d")
        return [
            {"med_id": r.med_id, "slot": r.slot, "status": r.status.value, "due_at": r.due_at.isoformat()}
            for r in repo.list_dose_records(user_id, today)
        ]

    return [
        StructuredTool.from_function(
            func=get_current_vitals, name="get_current_vitals",
            description="取得長者最新的血壓、心率與量測時間，並結合是否已確認危險警訊回傳風險等級（risk_level）",
            args_schema=GetCurrentVitalsArgs,
        ),
        StructuredTool.from_function(
            func=get_medication_plan, name="get_medication_plan",
            description="取得已確認（confirmed）的用藥計畫列表",
        ),
        StructuredTool.from_function(
            func=record_dose_self_report, name="record_dose_self_report",
            description="記錄使用者口頭回報已服藥", args_schema=RecordDoseArgs,
        ),
        StructuredTool.from_function(
            func=get_dose_history, name="get_dose_history",
            description="取得今日服藥紀錄狀態",
        ),
    ]
