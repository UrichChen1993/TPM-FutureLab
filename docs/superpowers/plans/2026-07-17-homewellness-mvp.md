# HomeWellness Companion MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the MVP described in `PRD.md` / `SRS.md`: a Streamlit chat app where a LangChain + Gemini agent proactively checks on an elderly user around dinner time, confirms meal/medication status, pulls simulated vitals when the user reports discomfort, applies a rule-based risk/escalation engine, and records everything to a pluggable storage backend (in-memory now, DynamoDB once credentials exist).

**Architecture:** Layered, framework-light: `domain` (states/models) → `storage` (Repository interface + memory/DynamoDB backends) → `rules` (pure risk + escalation logic, unit-testable without any LLM) → `simulator` (virtual clock + IoT event generators) → `agent` (LangChain tools/prompt/executor) → `app.py` (Streamlit wiring). Business logic never lives inside the LLM prompt — the agent only calls tools that delegate to `rules/`.

**Tech Stack:** Python, Streamlit, LangChain (`langchain`, `langchain-google-genai`), boto3, pytest.

## Global Constraints

- 互動介面：Streamlit 文字對話，畫面需標示 "Text-based simulation of voice interaction"；不做語音辨識/合成。(SRS UI-01)
- AI 工作流：Python + LangChain；LLM 透過 `LLM_PROVIDER`/`LLM_MODEL`/`LLM_API_KEY` 抽象，預設 provider 為 Gemini (`google_genai`)。(SRS AI-01)
- 儲存：`DATA_BACKEND` 環境變數切換 `memory` / `dynamodb`；DynamoDB 無法連線時必須明確顯示錯誤，不可假裝寫入成功。(SRS AWS-01)。**開發期間先用 `memory`**，AWS/Gemini 憑證尚未備妥（本次會談確認）。
- 家屬通知僅顯示於 Streamlit，不寄送真實 SMS/Email。(SRS NOTIFY-01)
- 藥袋 OCR 不在 MVP 範圍。(SRS OCR-01)
- 智慧藥盒為選配外接裝置，主流程不得依賴它才能運作。(SRS DEVICE-01)
- LLM 不自行制定醫療規則；風險分級與提醒升級一律由 `rules/` 內的規則函式決定，Agent 只能呼叫工具取得結果。(PRD §10)
- Demo 情境時間用「可控制的模擬時間 + 手動按鈕」觸發，不等待真實時間經過（本次會談確認）。
- 風險分級與提醒時間閾值目前沒有官方數值，本計畫採用以下預設值（全部集中在 `rules/config.py`，之後如有正式數據只需改這個檔案）：

  | 項目 | 預設值 |
  |---|---|
  | 血壓收縮壓危險 | ≥180 或 ≤90 mmHg |
  | 血壓舒張壓危險 | ≥120 mmHg |
  | 血壓收縮壓警示 | ≥160 mmHg |
  | 心率危險 | ≥120 或 ≤50 bpm |
  | 心率警示 | ≥100 或 ≤55 bpm |
  | 生理數據過期 | 量測時間超過 60 分鐘視為不可靠 |
  | 首次提醒延遲 | 應服藥時間後 20 分鐘 |
  | 二次提醒延遲 | 上次提醒後再 20 分鐘 |
  | 標記漏服（missed） | 應服藥時間後 60 分鐘仍未完成 |
  | 長時間無回應升級緊急通知 | 應服藥時間後 120 分鐘仍為 missed |

- 測試範疇：本機可執行 Demo + 針對規則引擎/工具/儲存層的 pytest 單元測試；不對外部 AWS/Gemini 做自動化整合測試（需要真實憑證時另行手動驗證）。（本次會談確認）

---

## File Structure

```
TPM-/
  requirements.txt
  .env.example
  .gitignore
  config.py
  seed_data.py
  app.py
  domain/
    __init__.py
    states.py
    models.py
  storage/
    __init__.py
    base.py
    memory_backend.py
    dynamodb_backend.py
    factory.py
  rules/
    __init__.py
    config.py
    risk_engine.py
    escalation_engine.py
  simulator/
    __init__.py
    clock.py
    iot_simulator.py
  agent/
    __init__.py
    llm.py
    prompts.py
    tools.py
    agent.py
  scripts/
    create_dynamodb_table.py
  docs/
    demo-runbook.md
  tests/
    test_clock.py
    test_memory_backend.py
    test_risk_engine.py
    test_escalation_engine.py
    test_seed_data.py
    test_tools.py
    test_agent_build.py
    test_iot_simulator.py
    test_app_smoke.py
```

---

### Task 1: Project scaffolding & config

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `config.py`
- Create: `domain/__init__.py`, `storage/__init__.py`, `rules/__init__.py`, `simulator/__init__.py`, `agent/__init__.py` (all empty)

**Interfaces:**
- Produces: `config.Settings` dataclass and `config.load_settings() -> Settings` with fields `data_backend`, `aws_region`, `dynamodb_table`, `llm_provider`, `llm_model`, `llm_api_key`. Every later task that needs env-driven config imports this.

- [ ] **Step 1: Initialize git and folders**

```bash
git init
mkdir -p domain storage rules simulator agent scripts docs tests
touch domain/__init__.py storage/__init__.py rules/__init__.py simulator/__init__.py agent/__init__.py
```

- [ ] **Step 2: Write `requirements.txt`**

```text
streamlit
langchain
langchain-core
langchain-google-genai
boto3
python-dotenv
pytest
```

- [ ] **Step 3: Write `.env.example`**

```text
DATA_BACKEND=memory
AWS_REGION=ap-northeast-1
DYNAMODB_TABLE=homewellness-mvp
LLM_PROVIDER=google_genai
LLM_MODEL=gemini-1.5-flash
LLM_API_KEY=
```

- [ ] **Step 4: Write `.gitignore`**

```text
.venv/
__pycache__/
*.pyc
.env
```

- [ ] **Step 5: Write `config.py`**

```python
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    data_backend: str
    aws_region: str
    dynamodb_table: str
    llm_provider: str
    llm_model: str
    llm_api_key: str | None


def load_settings() -> Settings:
    return Settings(
        data_backend=os.getenv("DATA_BACKEND", "memory"),
        aws_region=os.getenv("AWS_REGION", "ap-northeast-1"),
        dynamodb_table=os.getenv("DYNAMODB_TABLE", "homewellness-mvp"),
        llm_provider=os.getenv("LLM_PROVIDER", "google_genai"),
        llm_model=os.getenv("LLM_MODEL", "gemini-1.5-flash"),
        llm_api_key=os.getenv("LLM_API_KEY") or None,
    )
```

- [ ] **Step 6: Install dependencies and verify config loads**

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -c "from config import load_settings; print(load_settings())"
```

Expected: prints `Settings(data_backend='memory', ...)` with no errors. (Trivial config loader — no dedicated test file, per YAGNI.)

- [ ] **Step 7: Commit**

```bash
git add requirements.txt .env.example .gitignore config.py domain storage rules simulator agent
git commit -m "chore: project scaffolding and env-driven config"
```

---

### Task 2: Domain states & models

**Files:**
- Create: `domain/states.py`
- Create: `domain/models.py`

**Interfaces:**
- Consumes: nothing.
- Produces: enums `MealStatus`, `DoseStatus`, `RiskLevel`, `NotificationSeverity`; dataclasses `MedicationPlan`, `VitalReading`, `IoTEvent`, `DoseRecord`, `Notification`. Every later task imports these.

- [ ] **Step 1: Write `domain/states.py`**

```python
from enum import Enum


class MealStatus(str, Enum):
    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"
    NOT_EATEN = "not_eaten"
    UNKNOWN = "unknown"


class DoseStatus(str, Enum):
    SCHEDULED = "scheduled"
    DUE = "due"
    REMINDED = "reminded"
    SELF_REPORTED = "self_reported"
    SENSOR_SUPPORTED = "sensor_supported"
    MISSED = "missed"
    NEEDS_REVIEW = "needs_review"


class RiskLevel(str, Enum):
    SAFE = "safe"
    WARNING = "warning"
    DANGER = "danger"
    UNKNOWN = "unknown"


class NotificationSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
```

- [ ] **Step 2: Write `domain/models.py`**

```python
from dataclasses import dataclass, field
from datetime import datetime

from domain.states import DoseStatus


@dataclass
class MedicationPlan:
    med_id: str
    user_id: str
    name: str
    dose: str
    timing: str  # "BEFORE_MEAL" | "AFTER_MEAL" | "FIXED_TIME"
    valid_from: datetime
    valid_to: datetime | None
    confirmed: bool
    created_by: str
    updated_at: datetime


@dataclass
class VitalReading:
    user_id: str
    systolic: int
    diastolic: int
    heart_rate: int
    measured_at: datetime
    source: str = "simulated_device"


@dataclass
class IoTEvent:
    user_id: str
    event_id: str
    event_type: str  # "MEAL_AREA_PRESENCE" | "PILLBOX_OPENED_WEIGHT_DROP"
    occurred_at: datetime
    payload: dict = field(default_factory=dict)


@dataclass
class DoseRecord:
    user_id: str
    date: str  # "YYYY-MM-DD"
    med_id: str
    slot: str  # "BREAKFAST" | "LUNCH" | "DINNER"
    status: DoseStatus
    due_at: datetime
    reminded_at: datetime | None = None
    completed_at: datetime | None = None
    source: str | None = None       # "voice" | "sensor" | "voice+sensor"
    confidence: str | None = None   # "self_reported" | "sensor_supported"


@dataclass
class Notification:
    user_id: str
    notification_id: str
    occurred_at: datetime
    reason: str
    severity: str  # NotificationSeverity value
    message: str
```

- [ ] **Step 3: Verify it imports cleanly**

```bash
.venv/Scripts/python -c "from domain.models import MedicationPlan; from domain.states import RiskLevel; print('ok')"
```

Expected: `ok`. (Plain dataclasses/enums — no behavior to unit test yet.)

- [ ] **Step 4: Commit**

```bash
git add domain
git commit -m "feat: domain states and models"
```

---

### Task 3: Simulated clock

**Files:**
- Create: `simulator/clock.py`
- Test: `tests/test_clock.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `SimClock` with `.now: datetime`, `.advance(minutes: int)`, `.jump_to_dinner()`, classmethod `SimClock.starting_at(dt)`. Used by every task from here on instead of `datetime.now()`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_clock.py
from datetime import datetime

from simulator.clock import SimClock


def test_advance_adds_minutes():
    clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))
    clock.advance(30)
    assert clock.now == datetime(2026, 7, 17, 18, 0)


def test_jump_to_dinner_sets_18_00():
    clock = SimClock.starting_at(datetime(2026, 7, 17, 14, 5))
    clock.jump_to_dinner()
    assert clock.now == datetime(2026, 7, 17, 18, 0, 0)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/Scripts/pytest tests/test_clock.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'simulator.clock'`.

- [ ] **Step 3: Write `simulator/clock.py`**

```python
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class SimClock:
    now: datetime

    @classmethod
    def starting_at(cls, dt: datetime) -> "SimClock":
        return cls(now=dt)

    def advance(self, minutes: int) -> None:
        self.now += timedelta(minutes=minutes)

    def jump_to_dinner(self) -> None:
        self.now = self.now.replace(hour=18, minute=0, second=0, microsecond=0)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/Scripts/pytest tests/test_clock.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add simulator/clock.py tests/test_clock.py
git commit -m "feat: simulated clock for demo time control"
```

---

### Task 4: In-memory storage backend

**Files:**
- Create: `storage/base.py`
- Create: `storage/memory_backend.py`
- Test: `tests/test_memory_backend.py`

**Interfaces:**
- Consumes: `domain.models.*`, `domain.states.DoseStatus`.
- Produces: abstract `Repository` with methods `get_medication_plans`, `seed_medication_plan`, `put_vital`, `get_latest_vital`, `put_iot_event`, `put_dose_record`, `get_dose_record`, `list_dose_records`, `put_notification`, `list_notifications`; concrete `InMemoryRepository`. Task 6, 7, 9, 11, 12 all depend on this exact interface.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_memory_backend.py
from datetime import datetime

from domain.models import DoseRecord, MedicationPlan, Notification, VitalReading
from domain.states import DoseStatus
from storage.memory_backend import InMemoryRepository


def make_plan():
    now = datetime(2026, 7, 17, 8, 0)
    return MedicationPlan(
        med_id="med-001", user_id="user-001", name="脈康錠 5mg", dose="1顆",
        timing="AFTER_MEAL", valid_from=now, valid_to=None,
        confirmed=True, created_by="family-001", updated_at=now,
    )


def test_seed_and_get_medication_plans():
    repo = InMemoryRepository()
    repo.seed_medication_plan(make_plan())
    plans = repo.get_medication_plans("user-001")
    assert len(plans) == 1
    assert plans[0].med_id == "med-001"


def test_latest_vital_returns_most_recent():
    repo = InMemoryRepository()
    repo.put_vital(VitalReading(
        user_id="user-001", systolic=120, diastolic=80, heart_rate=70,
        measured_at=datetime(2026, 7, 17, 17, 0),
    ))
    repo.put_vital(VitalReading(
        user_id="user-001", systolic=125, diastolic=82, heart_rate=72,
        measured_at=datetime(2026, 7, 17, 18, 0),
    ))
    latest = repo.get_latest_vital("user-001")
    assert latest.measured_at == datetime(2026, 7, 17, 18, 0)


def test_dose_record_round_trip():
    repo = InMemoryRepository()
    record = DoseRecord(
        user_id="user-001", date="2026-07-17", med_id="med-001", slot="DINNER",
        status=DoseStatus.SCHEDULED, due_at=datetime(2026, 7, 17, 18, 0),
    )
    repo.put_dose_record(record)
    fetched = repo.get_dose_record("user-001", "2026-07-17", "med-001", "DINNER")
    assert fetched.status == DoseStatus.SCHEDULED
    assert repo.list_dose_records("user-001", "2026-07-17") == [fetched]


def test_notifications_accumulate():
    repo = InMemoryRepository()
    repo.put_notification(Notification(
        user_id="user-001", notification_id="n1", occurred_at=datetime(2026, 7, 17, 19, 0),
        reason="dose_missed", severity="medium", message="漏服",
    ))
    assert len(repo.list_notifications("user-001")) == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/Scripts/pytest tests/test_memory_backend.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'storage.memory_backend'`.

- [ ] **Step 3: Write `storage/base.py`**

```python
from abc import ABC, abstractmethod

from domain.models import DoseRecord, IoTEvent, MedicationPlan, Notification, VitalReading


class Repository(ABC):
    @abstractmethod
    def get_medication_plans(self, user_id: str) -> list[MedicationPlan]: ...

    @abstractmethod
    def seed_medication_plan(self, plan: MedicationPlan) -> None: ...

    @abstractmethod
    def put_vital(self, vital: VitalReading) -> None: ...

    @abstractmethod
    def get_latest_vital(self, user_id: str) -> VitalReading | None: ...

    @abstractmethod
    def put_iot_event(self, event: IoTEvent) -> None: ...

    @abstractmethod
    def put_dose_record(self, record: DoseRecord) -> None: ...

    @abstractmethod
    def get_dose_record(self, user_id: str, date: str, med_id: str, slot: str) -> DoseRecord | None: ...

    @abstractmethod
    def list_dose_records(self, user_id: str, date: str) -> list[DoseRecord]: ...

    @abstractmethod
    def put_notification(self, notification: Notification) -> None: ...

    @abstractmethod
    def list_notifications(self, user_id: str) -> list[Notification]: ...
```

- [ ] **Step 4: Write `storage/memory_backend.py`**

```python
from domain.models import DoseRecord, IoTEvent, MedicationPlan, Notification, VitalReading
from storage.base import Repository


class InMemoryRepository(Repository):
    def __init__(self):
        self._plans: dict[str, list[MedicationPlan]] = {}
        self._vitals: dict[str, list[VitalReading]] = {}
        self._iot_events: dict[str, list[IoTEvent]] = {}
        self._doses: dict[tuple[str, str, str, str], DoseRecord] = {}
        self._notifications: dict[str, list[Notification]] = {}

    def seed_medication_plan(self, plan: MedicationPlan) -> None:
        self._plans.setdefault(plan.user_id, []).append(plan)

    def get_medication_plans(self, user_id: str) -> list[MedicationPlan]:
        return list(self._plans.get(user_id, []))

    def put_vital(self, vital: VitalReading) -> None:
        self._vitals.setdefault(vital.user_id, []).append(vital)

    def get_latest_vital(self, user_id: str) -> VitalReading | None:
        readings = self._vitals.get(user_id, [])
        if not readings:
            return None
        return max(readings, key=lambda v: v.measured_at)

    def put_iot_event(self, event: IoTEvent) -> None:
        self._iot_events.setdefault(event.user_id, []).append(event)

    def put_dose_record(self, record: DoseRecord) -> None:
        self._doses[(record.user_id, record.date, record.med_id, record.slot)] = record

    def get_dose_record(self, user_id: str, date: str, med_id: str, slot: str) -> DoseRecord | None:
        return self._doses.get((user_id, date, med_id, slot))

    def list_dose_records(self, user_id: str, date: str) -> list[DoseRecord]:
        return [
            record for (uid, d, _, _), record in self._doses.items()
            if uid == user_id and d == date
        ]

    def put_notification(self, notification: Notification) -> None:
        self._notifications.setdefault(notification.user_id, []).append(notification)

    def list_notifications(self, user_id: str) -> list[Notification]:
        return list(self._notifications.get(user_id, []))
```

- [ ] **Step 5: Run test to verify it passes**

```bash
.venv/Scripts/pytest tests/test_memory_backend.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add storage/base.py storage/memory_backend.py tests/test_memory_backend.py
git commit -m "feat: Repository interface and in-memory backend"
```

---

### Task 5: Risk rule engine

**Files:**
- Create: `rules/config.py`
- Create: `rules/risk_engine.py`
- Test: `tests/test_risk_engine.py`

**Interfaces:**
- Consumes: `domain.states.RiskLevel`.
- Produces: `classify_vitals(systolic, diastolic, heart_rate, measured_at, now) -> RiskLevel`, `has_danger_symptom(text: str) -> bool`, `combine_risk(vitals_risk, danger_symptom_confirmed: bool) -> RiskLevel`. Task 9 (agent tools) calls these directly.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_risk_engine.py
from datetime import datetime

from domain.states import RiskLevel
from rules.risk_engine import classify_vitals, combine_risk, has_danger_symptom


def test_normal_vitals_are_safe():
    now = datetime(2026, 7, 17, 18, 0)
    risk = classify_vitals(120, 80, 70, measured_at=now, now=now)
    assert risk == RiskLevel.SAFE


def test_high_heart_rate_is_danger():
    now = datetime(2026, 7, 17, 18, 0)
    risk = classify_vitals(120, 80, 130, measured_at=now, now=now)
    assert risk == RiskLevel.DANGER


def test_borderline_systolic_is_warning():
    now = datetime(2026, 7, 17, 18, 0)
    risk = classify_vitals(165, 80, 70, measured_at=now, now=now)
    assert risk == RiskLevel.WARNING


def test_stale_vitals_are_unknown():
    measured_at = datetime(2026, 7, 17, 16, 0)
    now = datetime(2026, 7, 17, 18, 0)
    risk = classify_vitals(120, 80, 70, measured_at=measured_at, now=now)
    assert risk == RiskLevel.UNKNOWN


def test_has_danger_symptom_detects_keyword():
    assert has_danger_symptom("我有胸痛的感覺") is True
    assert has_danger_symptom("只是有點累") is False


def test_combine_risk_danger_symptom_overrides():
    assert combine_risk(RiskLevel.SAFE, danger_symptom_confirmed=True) == RiskLevel.DANGER


def test_combine_risk_unknown_vitals_falls_back_to_warning():
    assert combine_risk(RiskLevel.UNKNOWN, danger_symptom_confirmed=False) == RiskLevel.WARNING
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/Scripts/pytest tests/test_risk_engine.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'rules.risk_engine'`.

- [ ] **Step 3: Write `rules/config.py`**

```python
# Risk thresholds and escalation timings.
# ponytail: values are MVP defaults with no clinical source; adjust here if a real
# medical guideline is provided later — nothing else in the codebase should change.

BP_SYSTOLIC_DANGER_HIGH = 180
BP_SYSTOLIC_DANGER_LOW = 90
BP_DIASTOLIC_DANGER_HIGH = 120
BP_SYSTOLIC_WARNING_HIGH = 160

HR_DANGER_HIGH = 120
HR_DANGER_LOW = 50
HR_WARNING_HIGH = 100
HR_WARNING_LOW = 55

VITAL_STALE_MINUTES = 60

DANGER_SYMPTOMS = ["胸痛", "呼吸困難", "意識不清", "劇烈疼痛", "無法起身"]

FIRST_REMINDER_DELAY_MINUTES = 20
SECOND_REMINDER_DELAY_MINUTES = 20
MISSED_THRESHOLD_MINUTES = 60
EMERGENCY_UNRESPONSIVE_MINUTES = 120
```

- [ ] **Step 4: Write `rules/risk_engine.py`**

```python
from datetime import datetime

from domain.states import RiskLevel
from rules.config import (
    BP_DIASTOLIC_DANGER_HIGH,
    BP_SYSTOLIC_DANGER_HIGH,
    BP_SYSTOLIC_DANGER_LOW,
    BP_SYSTOLIC_WARNING_HIGH,
    DANGER_SYMPTOMS,
    HR_DANGER_HIGH,
    HR_DANGER_LOW,
    HR_WARNING_HIGH,
    HR_WARNING_LOW,
    VITAL_STALE_MINUTES,
)


def classify_vitals(
    systolic: int, diastolic: int, heart_rate: int, measured_at: datetime, now: datetime
) -> RiskLevel:
    age_minutes = (now - measured_at).total_seconds() / 60
    if age_minutes > VITAL_STALE_MINUTES:
        return RiskLevel.UNKNOWN

    if (
        systolic >= BP_SYSTOLIC_DANGER_HIGH
        or systolic <= BP_SYSTOLIC_DANGER_LOW
        or diastolic >= BP_DIASTOLIC_DANGER_HIGH
        or heart_rate >= HR_DANGER_HIGH
        or heart_rate <= HR_DANGER_LOW
    ):
        return RiskLevel.DANGER

    if systolic >= BP_SYSTOLIC_WARNING_HIGH or heart_rate >= HR_WARNING_HIGH or heart_rate <= HR_WARNING_LOW:
        return RiskLevel.WARNING

    return RiskLevel.SAFE


def has_danger_symptom(reported_text: str) -> bool:
    return any(keyword in reported_text for keyword in DANGER_SYMPTOMS)


def combine_risk(vitals_risk: RiskLevel, danger_symptom_confirmed: bool) -> RiskLevel:
    if danger_symptom_confirmed:
        return RiskLevel.DANGER
    if vitals_risk == RiskLevel.UNKNOWN:
        return RiskLevel.WARNING
    return vitals_risk
```

- [ ] **Step 5: Run test to verify it passes**

```bash
.venv/Scripts/pytest tests/test_risk_engine.py -v
```

Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add rules/config.py rules/risk_engine.py tests/test_risk_engine.py
git commit -m "feat: rule-based vitals risk classification"
```

---

### Task 6: Escalation rule engine

**Files:**
- Create: `rules/escalation_engine.py`
- Test: `tests/test_escalation_engine.py`

**Interfaces:**
- Consumes: `storage.base.Repository`, `storage.memory_backend.InMemoryRepository` (tests only), `domain.models.DoseRecord`, `domain.models.Notification`, `domain.states.DoseStatus`, `domain.states.NotificationSeverity`, `rules.config.*`.
- Produces: `evaluate_dose(record, now) -> EscalationResult`, `apply_escalation(repo, record, now) -> EscalationResult` (writes back to repo, idempotent notifications), `ensure_today_doses(repo, clock, user_id)`. Task 9 and 12 call `apply_escalation`/`ensure_today_doses`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_escalation_engine.py
from datetime import datetime, timedelta

from domain.models import DoseRecord, MedicationPlan
from domain.states import DoseStatus
from rules.escalation_engine import apply_escalation, ensure_today_doses, evaluate_dose
from simulator.clock import SimClock
from storage.memory_backend import InMemoryRepository


def make_record(status=DoseStatus.SCHEDULED, due_at=None, reminded_at=None):
    return DoseRecord(
        user_id="user-001", date="2026-07-17", med_id="med-001", slot="DINNER",
        status=status, due_at=due_at or datetime(2026, 7, 17, 18, 0), reminded_at=reminded_at,
    )


def test_before_due_stays_scheduled():
    record = make_record()
    now = datetime(2026, 7, 17, 17, 0)
    result = evaluate_dose(record, now)
    assert result.new_status == DoseStatus.SCHEDULED
    assert result.send_reminder is False


def test_at_due_time_becomes_due():
    record = make_record()
    now = datetime(2026, 7, 17, 18, 0)
    result = evaluate_dose(record, now)
    assert result.new_status == DoseStatus.DUE


def test_20_minutes_after_due_sends_first_reminder():
    record = make_record(status=DoseStatus.DUE)
    now = datetime(2026, 7, 17, 18, 20)
    result = evaluate_dose(record, now)
    assert result.new_status == DoseStatus.REMINDED
    assert result.send_reminder is True


def test_60_minutes_after_due_is_missed_with_medium_notification():
    record = make_record(status=DoseStatus.REMINDED, reminded_at=datetime(2026, 7, 17, 18, 40))
    now = datetime(2026, 7, 17, 19, 0)
    result = evaluate_dose(record, now)
    assert result.new_status == DoseStatus.MISSED
    assert result.notify_severity == "medium"


def test_120_minutes_after_due_escalates_to_high():
    record = make_record(status=DoseStatus.MISSED)
    now = datetime(2026, 7, 17, 20, 0)
    result = evaluate_dose(record, now)
    assert result.new_status == DoseStatus.MISSED
    assert result.notify_severity == "high"


def test_self_reported_dose_has_no_further_action():
    record = make_record(status=DoseStatus.SELF_REPORTED)
    result = evaluate_dose(record, datetime(2026, 7, 17, 23, 0))
    assert result.new_status == DoseStatus.SELF_REPORTED
    assert result.send_reminder is False
    assert result.notify_severity is None


def test_apply_escalation_writes_dose_and_avoids_duplicate_notifications():
    repo = InMemoryRepository()
    record = make_record(status=DoseStatus.REMINDED, reminded_at=datetime(2026, 7, 17, 18, 40))
    repo.put_dose_record(record)
    now = datetime(2026, 7, 17, 19, 0)

    apply_escalation(repo, record, now)
    apply_escalation(repo, record, now)  # second call must not duplicate the notification

    stored = repo.get_dose_record("user-001", "2026-07-17", "med-001", "DINNER")
    assert stored.status == DoseStatus.MISSED
    assert len(repo.list_notifications("user-001")) == 1


def test_ensure_today_doses_creates_scheduled_record_from_confirmed_plan():
    repo = InMemoryRepository()
    now = datetime(2026, 7, 17, 8, 0)
    repo.seed_medication_plan(MedicationPlan(
        med_id="med-001", user_id="user-001", name="脈康錠 5mg", dose="1顆",
        timing="AFTER_MEAL", valid_from=now, valid_to=None,
        confirmed=True, created_by="family-001", updated_at=now,
    ))
    clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))

    ensure_today_doses(repo, clock, "user-001")

    records = repo.list_dose_records("user-001", "2026-07-17")
    assert len(records) == 1
    assert records[0].slot == "DINNER"
    assert records[0].status == DoseStatus.SCHEDULED
    assert records[0].due_at == datetime(2026, 7, 17, 18, 0)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/Scripts/pytest tests/test_escalation_engine.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'rules.escalation_engine'`.

- [ ] **Step 3: Write `rules/escalation_engine.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/Scripts/pytest tests/test_escalation_engine.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add rules/escalation_engine.py tests/test_escalation_engine.py
git commit -m "feat: dose reminder escalation and daily dose scheduling"
```

---

### Task 7: DynamoDB backend & storage factory

**Files:**
- Create: `storage/dynamodb_backend.py`
- Create: `storage/factory.py`
- Create: `scripts/create_dynamodb_table.py`

**Interfaces:**
- Consumes: `storage.base.Repository`, `config.load_settings`.
- Produces: `DynamoDBRepository` implementing `Repository` over a single table (`PK`/`SK` design from SRS §AWS-01); `get_repository() -> Repository` reading `DATA_BACKEND`. Task 12 (`app.py`) calls `get_repository()` exclusively — it never imports a concrete backend directly.

**No automated AWS test in this task** — AWS credentials aren't available yet (confirmed with user). This backend is verified manually once credentials exist (see Task 13 runbook). It's still written now because SRS AWS-01 requires it and Task 12's `DATA_BACKEND=dynamodb` switch needs a real implementation to switch to.

- [ ] **Step 1: Write `storage/dynamodb_backend.py`**

```python
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
```

- [ ] **Step 2: Write `storage/factory.py`**

```python
from config import load_settings
from storage.base import Repository
from storage.dynamodb_backend import DynamoDBRepository
from storage.memory_backend import InMemoryRepository


def get_repository() -> Repository:
    settings = load_settings()
    if settings.data_backend == "dynamodb":
        return DynamoDBRepository(table_name=settings.dynamodb_table, region=settings.aws_region)
    return InMemoryRepository()
```

- [ ] **Step 3: Write `scripts/create_dynamodb_table.py`**

```python
"""Run once, after AWS credentials are available, to create the MVP table.

Usage: python scripts/create_dynamodb_table.py
"""
import boto3

from config import load_settings


def main() -> None:
    settings = load_settings()
    client = boto3.client("dynamodb", region_name=settings.aws_region)
    client.create_table(
        TableName=settings.dynamodb_table,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    print(f"created table {settings.dynamodb_table} in {settings.aws_region}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Verify the memory path still works through the factory**

```bash
.venv/Scripts/python -c "from storage.factory import get_repository; r = get_repository(); print(type(r).__name__)"
```

Expected: `InMemoryRepository` (since `DATA_BACKEND` defaults to `memory`). The `dynamodb` path is verified manually per the Task 13 runbook once AWS credentials exist.

- [ ] **Step 5: Commit**

```bash
git add storage/dynamodb_backend.py storage/factory.py scripts/create_dynamodb_table.py
git commit -m "feat: DynamoDB repository and backend-switching factory"
```

---

### Task 8: Seed data

**Files:**
- Create: `seed_data.py`
- Test: `tests/test_seed_data.py`

**Interfaces:**
- Consumes: `storage.base.Repository`, `storage.factory.get_repository`, `domain.models.MedicationPlan`.
- Produces: `seed_demo_user(repo, user_id="user-001")`. Task 12 calls this on app startup (US-01: MVP 可預先載入用藥資料).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_seed_data.py
from seed_data import seed_demo_user
from storage.memory_backend import InMemoryRepository


def test_seed_demo_user_creates_confirmed_plan():
    repo = InMemoryRepository()
    seed_demo_user(repo, "user-001")
    plans = repo.get_medication_plans("user-001")
    assert len(plans) == 1
    assert plans[0].confirmed is True
    assert plans[0].timing == "AFTER_MEAL"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/Scripts/pytest tests/test_seed_data.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'seed_data'`.

- [ ] **Step 3: Write `seed_data.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/Scripts/pytest tests/test_seed_data.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add seed_data.py tests/test_seed_data.py
git commit -m "feat: preloaded demo medication plan (US-01)"
```

---

### Task 9: Agent tools

**Files:**
- Create: `agent/tools.py`
- Test: `tests/test_tools.py`

**Interfaces:**
- Consumes: `storage.base.Repository`, `simulator.clock.SimClock`, `rules.risk_engine.classify_vitals`, `domain.states.DoseStatus`.
- Produces: `build_tools(repo, clock, user_id) -> list[StructuredTool]` exposing `get_current_vitals`, `get_medication_plan`, `record_dose_self_report`, `get_dose_history`. Task 10 (`agent.agent.build_agent_executor`) consumes this list directly.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tools.py
from datetime import datetime

from agent.tools import build_tools
from domain.models import DoseRecord, MedicationPlan, VitalReading
from domain.states import DoseStatus
from simulator.clock import SimClock
from storage.memory_backend import InMemoryRepository


def make_repo_with_fixtures(now: datetime) -> InMemoryRepository:
    repo = InMemoryRepository()
    repo.seed_medication_plan(MedicationPlan(
        med_id="med-001", user_id="user-001", name="脈康錠 5mg", dose="1顆",
        timing="AFTER_MEAL", valid_from=now, valid_to=None,
        confirmed=True, created_by="family-001", updated_at=now,
    ))
    repo.put_vital(VitalReading(
        user_id="user-001", systolic=120, diastolic=80, heart_rate=72, measured_at=now,
    ))
    repo.put_dose_record(DoseRecord(
        user_id="user-001", date=now.strftime("%Y-%m-%d"), med_id="med-001", slot="DINNER",
        status=DoseStatus.DUE, due_at=now,
    ))
    return repo


def get_tool(tools, name):
    return next(t for t in tools if t.name == name)


def test_get_current_vitals_reports_risk_level():
    now = datetime(2026, 7, 17, 18, 0)
    repo = make_repo_with_fixtures(now)
    clock = SimClock.starting_at(now)
    tools = build_tools(repo, clock, "user-001")

    result = get_tool(tools, "get_current_vitals").invoke({})

    assert result["available"] is True
    assert result["risk_level"] == "safe"


def test_get_medication_plan_returns_confirmed_only():
    now = datetime(2026, 7, 17, 18, 0)
    repo = make_repo_with_fixtures(now)
    clock = SimClock.starting_at(now)
    tools = build_tools(repo, clock, "user-001")

    result = get_tool(tools, "get_medication_plan").invoke({})

    assert result == [{"med_id": "med-001", "name": "脈康錠 5mg", "dose": "1顆", "timing": "AFTER_MEAL"}]


def test_record_dose_self_report_updates_status():
    now = datetime(2026, 7, 17, 18, 0)
    repo = make_repo_with_fixtures(now)
    clock = SimClock.starting_at(now)
    tools = build_tools(repo, clock, "user-001")

    result = get_tool(tools, "record_dose_self_report").invoke({"med_id": "med-001", "slot": "DINNER"})

    assert result == {"ok": True, "status": "self_reported"}
    stored = repo.get_dose_record("user-001", "2026-07-17", "med-001", "DINNER")
    assert stored.status == DoseStatus.SELF_REPORTED
    assert stored.confidence == "self_reported"


def test_get_dose_history_lists_today():
    now = datetime(2026, 7, 17, 18, 0)
    repo = make_repo_with_fixtures(now)
    clock = SimClock.starting_at(now)
    tools = build_tools(repo, clock, "user-001")

    result = get_tool(tools, "get_dose_history").invoke({})

    assert result == [{"med_id": "med-001", "slot": "DINNER", "status": "due", "due_at": now.isoformat()}]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/Scripts/pytest tests/test_tools.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent.tools'`.

- [ ] **Step 3: Write `agent/tools.py`**

```python
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from domain.states import DoseStatus
from rules.risk_engine import classify_vitals


class RecordDoseArgs(BaseModel):
    med_id: str = Field(description="要記錄的藥物 ID")
    slot: str = Field(description="服藥時段，例如 DINNER")


def build_tools(repo, clock, user_id: str) -> list[StructuredTool]:
    def get_current_vitals() -> dict:
        vital = repo.get_latest_vital(user_id)
        if vital is None:
            return {"available": False, "reason": "no_data"}
        risk = classify_vitals(vital.systolic, vital.diastolic, vital.heart_rate, vital.measured_at, clock.now)
        return {
            "available": risk.value != "unknown",
            "systolic": vital.systolic,
            "diastolic": vital.diastolic,
            "heart_rate": vital.heart_rate,
            "measured_at": vital.measured_at.isoformat(),
            "source": vital.source,
            "risk_level": risk.value,
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
            description="取得長者最新的血壓、心率與量測時間，並附上風險等級（risk_level）",
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/Scripts/pytest tests/test_tools.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add agent/tools.py tests/test_tools.py
git commit -m "feat: LangChain tools bridging agent to rules and storage"
```

---

### Task 10: LLM + agent assembly

**Files:**
- Create: `agent/llm.py`
- Create: `agent/prompts.py`
- Create: `agent/agent.py`
- Test: `tests/test_agent_build.py`

**Interfaces:**
- Consumes: `config.load_settings`, `agent.tools.build_tools`.
- Produces: `build_llm()`, `build_agent_executor(repo, clock, user_id) -> AgentExecutor`. Task 12 (`app.py`) calls `build_agent_executor` and catches `ValueError` when `LLM_API_KEY` is unset.

**No live Gemini call in automated tests** — no API key available yet (confirmed with user). Test only the parts that don't need network: missing-key error and tool wiring. Full conversational behavior is verified manually once `LLM_API_KEY` is set (Task 13 runbook).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agent_build.py
import pytest

from agent.agent import build_agent_executor
from simulator.clock import SimClock
from storage.memory_backend import InMemoryRepository
from datetime import datetime


def test_build_agent_executor_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 18, 0))

    with pytest.raises(ValueError, match="LLM_API_KEY"):
        build_agent_executor(repo, clock, "user-001")


def test_build_agent_executor_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "dummy")
    monkeypatch.setenv("LLM_PROVIDER", "unknown_provider")
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 18, 0))

    with pytest.raises(ValueError, match="unsupported LLM_PROVIDER"):
        build_agent_executor(repo, clock, "user-001")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/Scripts/pytest tests/test_agent_build.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent.agent'`.

- [ ] **Step 3: Write `agent/llm.py`**

```python
from langchain_google_genai import ChatGoogleGenerativeAI

from config import load_settings


def build_llm():
    settings = load_settings()
    if settings.llm_provider != "google_genai":
        raise ValueError(f"unsupported LLM_PROVIDER: {settings.llm_provider}")
    if not settings.llm_api_key:
        raise ValueError("LLM_API_KEY is not set")
    return ChatGoogleGenerativeAI(model=settings.llm_model, google_api_key=settings.llm_api_key, temperature=0.3)
```

- [ ] **Step 4: Write `agent/prompts.py`**

```python
SYSTEM_PROMPT = """你是 HomeWellness Companion，一個居家關懷語音 Agent，服務對象是獨居或白天獨處的長者。

語氣原則：
- 溫暖但不過度擬人化。
- 簡短，一次只問一件事。
- 不責備、不說教。
- 重要資訊要重述確認。
- 清楚揭露資料無法取得或判斷不確定的情況。
- 不使用恐嚇式醫療語言。

安全原則（不可違反）：
- 你不能自行制定醫療規則或判斷風險等級，風險分級一律以工具回傳的 risk_level 為準。
- 用藥資訊只能來自 get_medication_plan 回傳的已確認計畫，不可自行假設劑量或藥名。
- 不建議使用者自行加量、補吃、停藥或換藥。
- 呼叫 get_current_vitals 後，必須說明資料來源與量測時間；若 available 為 false，清楚告知目前無法取得可靠讀值。
- 使用者提及頭暈等不適時，先簡短詢問是否有胸痛、呼吸困難等危險警訊，再呼叫 get_current_vitals 綜合判斷。
- 使用者口頭表示已服藥時，呼叫 record_dose_self_report 記錄；只能說「已記錄您的口頭回報」或「感測訊號支持已完成」，不要宣稱「已證明服藥」。
"""
```

- [ ] **Step 5: Write `agent/agent.py`**

```python
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from agent.llm import build_llm
from agent.prompts import SYSTEM_PROMPT
from agent.tools import build_tools


def build_agent_executor(repo, clock, user_id: str) -> AgentExecutor:
    llm = build_llm()
    tools = build_tools(repo, clock, user_id)
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=False)
```

- [ ] **Step 6: Run test to verify it passes**

```bash
.venv/Scripts/pytest tests/test_agent_build.py -v
```

Expected: 2 passed. (`build_llm()` raises before any network call, so no API key is needed for this test.)

- [ ] **Step 7: Commit**

```bash
git add agent/llm.py agent/prompts.py agent/agent.py tests/test_agent_build.py
git commit -m "feat: Gemini-backed LangChain agent assembly"
```

---

### Task 11: IoT event simulator

**Files:**
- Create: `simulator/iot_simulator.py`
- Test: `tests/test_iot_simulator.py`

**Interfaces:**
- Consumes: `storage.base.Repository`, `simulator.clock.SimClock`, `domain.models.IoTEvent`, `domain.states.DoseStatus`.
- Produces: `simulate_meal_area_event(repo, clock, user_id) -> IoTEvent`, `simulate_pillbox_event(repo, clock, user_id, med_id, slot) -> tuple[IoTEvent, DoseRecord | None]`. Task 12's sidebar buttons call these.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_iot_simulator.py
from datetime import datetime

from domain.models import DoseRecord
from domain.states import DoseStatus
from simulator.clock import SimClock
from simulator.iot_simulator import simulate_meal_area_event, simulate_pillbox_event
from storage.memory_backend import InMemoryRepository


def test_simulate_meal_area_event_is_recorded():
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 18, 0))

    event = simulate_meal_area_event(repo, clock, "user-001")

    assert event.event_type == "MEAL_AREA_PRESENCE"


def test_simulate_pillbox_event_upgrades_dose_to_sensor_supported():
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 18, 30))
    repo.put_dose_record(DoseRecord(
        user_id="user-001", date="2026-07-17", med_id="med-001", slot="DINNER",
        status=DoseStatus.SELF_REPORTED, due_at=datetime(2026, 7, 17, 18, 0), source="voice",
    ))

    event, record = simulate_pillbox_event(repo, clock, "user-001", "med-001", "DINNER")

    assert event.event_type == "PILLBOX_OPENED_WEIGHT_DROP"
    assert record.status == DoseStatus.SENSOR_SUPPORTED
    assert record.source == "voice+sensor"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/Scripts/pytest tests/test_iot_simulator.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'simulator.iot_simulator'`.

- [ ] **Step 3: Write `simulator/iot_simulator.py`**

```python
import uuid

from domain.models import DoseRecord, IoTEvent
from domain.states import DoseStatus


def simulate_meal_area_event(repo, clock, user_id: str) -> IoTEvent:
    event = IoTEvent(
        user_id=user_id, event_id=f"evt-{uuid.uuid4().hex[:8]}",
        event_type="MEAL_AREA_PRESENCE", occurred_at=clock.now, payload={"zone": "dining_table"},
    )
    repo.put_iot_event(event)
    return event


def simulate_pillbox_event(
    repo, clock, user_id: str, med_id: str, slot: str
) -> tuple[IoTEvent, DoseRecord | None]:
    event = IoTEvent(
        user_id=user_id, event_id=f"evt-{uuid.uuid4().hex[:8]}",
        event_type="PILLBOX_OPENED_WEIGHT_DROP", occurred_at=clock.now,
        payload={"med_id": med_id, "slot": slot},
    )
    repo.put_iot_event(event)

    today = clock.now.strftime("%Y-%m-%d")
    record = repo.get_dose_record(user_id, today, med_id, slot)
    if record is not None and record.status != DoseStatus.SENSOR_SUPPORTED:
        record.status = DoseStatus.SENSOR_SUPPORTED
        record.confidence = "sensor_supported"
        record.completed_at = clock.now
        record.source = f"{record.source}+sensor" if record.source else "sensor"
        repo.put_dose_record(record)
    return event, record
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/Scripts/pytest tests/test_iot_simulator.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add simulator/iot_simulator.py tests/test_iot_simulator.py
git commit -m "feat: simulated meal-area and pillbox IoT events"
```

---

### Task 12: Streamlit UI

**Files:**
- Create: `app.py`
- Test: `tests/test_app_smoke.py`

**Interfaces:**
- Consumes: everything from Tasks 1–11 (`config`, `storage.factory.get_repository`, `seed_data.seed_demo_user`, `simulator.clock.SimClock`, `simulator.iot_simulator.*`, `rules.escalation_engine.ensure_today_doses`/`apply_escalation`, `agent.agent.build_agent_executor`).
- Produces: the runnable Streamlit entrypoint. Nothing downstream depends on this.

- [ ] **Step 1: Write the smoke test**

```python
# tests/test_app_smoke.py
import importlib


def test_app_module_imports_without_running_streamlit():
    module = importlib.import_module("app")
    assert hasattr(module, "main")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/Scripts/pytest tests/test_app_smoke.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app'`.

- [ ] **Step 3: Write `app.py`**

```python
from datetime import datetime

import streamlit as st

from agent.agent import build_agent_executor
from config import load_settings
from rules.escalation_engine import apply_escalation, ensure_today_doses
from seed_data import seed_demo_user
from simulator.clock import SimClock
from simulator.iot_simulator import simulate_meal_area_event, simulate_pillbox_event
from storage.factory import get_repository

USER_ID = "user-001"


def init_state() -> None:
    if "repo" not in st.session_state:
        st.session_state.repo = get_repository()
        seed_demo_user(st.session_state.repo, USER_ID)
    if "clock" not in st.session_state:
        st.session_state.clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "agent_executor" not in st.session_state:
        try:
            st.session_state.agent_executor = build_agent_executor(
                st.session_state.repo, st.session_state.clock, USER_ID
            )
            st.session_state.agent_error = None
        except ValueError as exc:
            st.session_state.agent_executor = None
            st.session_state.agent_error = str(exc)


def run_escalation_tick() -> None:
    repo, clock = st.session_state.repo, st.session_state.clock
    ensure_today_doses(repo, clock, USER_ID)
    for record in repo.list_dose_records(USER_ID, clock.now.strftime("%Y-%m-%d")):
        apply_escalation(repo, record, clock.now)


def render_sidebar() -> None:
    settings = load_settings()
    st.sidebar.subheader("系統狀態")
    st.sidebar.write(f"Backend：{settings.data_backend}")
    if settings.data_backend == "dynamodb":
        st.sidebar.write(f"Region：{settings.aws_region}")
    st.sidebar.write(f"模擬時間：{st.session_state.clock.now.isoformat()}")

    st.sidebar.subheader("情境模擬")
    if st.sidebar.button("模擬：晚餐時段感測事件"):
        st.session_state.clock.jump_to_dinner()
        simulate_meal_area_event(st.session_state.repo, st.session_state.clock, USER_ID)
        run_escalation_tick()
    if st.sidebar.button("前進 30 分鐘"):
        st.session_state.clock.advance(30)
        run_escalation_tick()
    if st.sidebar.button("模擬：藥盒開啟＋重量下降"):
        simulate_pillbox_event(st.session_state.repo, st.session_state.clock, USER_ID, "med-001", "DINNER")
        run_escalation_tick()

    st.sidebar.subheader("家屬通知")
    for note in st.session_state.repo.list_notifications(USER_ID):
        st.sidebar.warning(f"[{note.severity}] {note.message}（{note.occurred_at.isoformat()}）")


def render_chat() -> None:
    st.title("HomeWellness Companion")
    st.caption("Text-based simulation of voice interaction")

    for role, content in st.session_state.messages:
        st.chat_message(role).write(content)

    if st.session_state.agent_error:
        st.info(f"LLM 尚未設定（{st.session_state.agent_error}），僅能使用左側模擬按鈕測試流程。")
        return

    user_input = st.chat_input("輸入長者的回應...")
    if user_input:
        st.session_state.messages.append(("human", user_input))
        chat_history = [
            ("human", content) if role == "human" else ("ai", content)
            for role, content in st.session_state.messages[:-1]
        ]
        result = st.session_state.agent_executor.invoke({"input": user_input, "chat_history": chat_history})
        st.session_state.messages.append(("ai", result["output"]))
        st.rerun()


def main() -> None:
    st.set_page_config(page_title="HomeWellness Companion")
    init_state()
    render_sidebar()
    render_chat()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/Scripts/pytest tests/test_app_smoke.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Manually run the app**

```bash
.venv/Scripts/streamlit run app.py
```

Expected: browser opens, sidebar shows `Backend：memory` and the info banner "LLM 尚未設定（LLM_API_KEY is not set）..." since no Gemini key is configured yet. Clicking "模擬：晚餐時段感測事件" then "前進 30 分鐘" repeatedly should move a dose from `scheduled` → `due` → `reminded` → `missed`, with a notification appearing in the sidebar at the `missed` transition.

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_app_smoke.py
git commit -m "feat: Streamlit UI wiring chat, simulation controls, and notifications"
```

---

### Task 13: Demo runbook & credential cutover checklist

**Files:**
- Create: `docs/demo-runbook.md`

**Interfaces:**
- Consumes: none (documentation only).
- Produces: a written walkthrough for the Live Demo scenario (PRD §12 / SRS 最終主線) plus the steps to flip on real DynamoDB/Gemini once credentials arrive.

- [ ] **Step 1: Write `docs/demo-runbook.md`**

```markdown
# Demo Runbook

## 開發模式（目前，無 AWS / Gemini 憑證）

1. `DATA_BACKEND=memory`，`.env` 中 `LLM_API_KEY` 留空。
2. `streamlit run app.py`。
3. 側欄會顯示 `Backend：memory` 及「LLM 尚未設定」提示；此時無法測試對話，
   但可用側欄按鈕驗證模擬時間、IoT 事件與升級提醒的完整規則流程
   （對應 tests/test_escalation_engine.py 涵蓋的情境）。

## 取得憑證後的切換步驟

1. AWS：設定 AWS CLI profile 或環境變數提供憑證，執行一次
   `python scripts/create_dynamodb_table.py` 建立資料表，然後在 `.env`
   設定 `DATA_BACKEND=dynamodb`。
2. Gemini：在 `.env` 設定 `LLM_API_KEY=<key>`；如需更換模型調整
   `LLM_MODEL`（依當時官方可用模型與額度確認，SRS 刻意未寫死版本）。
3. 重新啟動 `streamlit run app.py`，側欄應顯示
   `Backend：dynamodb` 與正確的 `Region`。

## Live Demo 主線（PRD §12 / SRS 最終主線，目標 3–5 分鐘）

1. 點擊「模擬：晚餐時段感測事件」→ Agent 主動詢問是否已用餐。
2. 在對話框輸入：「吃完了，但今天有點頭暈。」
3. Agent 應先詢問是否有胸痛、呼吸困難等危險警訊，再呼叫
   `get_current_vitals`，並說明資料來源與量測時間。
4. Agent 依已確認計畫（`get_medication_plan`）提醒服藥。
5. 使用者回報「吃藥了」→ Agent 呼叫 `record_dose_self_report`。
6. 點擊「模擬：藥盒開啟＋重量下降」→ 服藥紀錄升級為 `sensor_supported`。
7. 側欄顯示更新後的服藥狀態與（如有觸發）家屬通知。

## 驗證未回應情境

1. 點擊「模擬：晚餐時段感測事件」後不輸入任何訊息。
2. 連續點擊「前進 30 分鐘」：
   - 第 1 次（due+20~30 分）→ 狀態變 `reminded`。
   - 第 2 次（due+60 分）→ 狀態變 `missed`，側欄出現 medium 通知。
   - 第 4 次（due+120 分）→ 側欄出現 high 通知（長時間無回應升級）。
```

- [ ] **Step 2: Commit**

```bash
git add docs/demo-runbook.md
git commit -m "docs: demo runbook and AWS/Gemini credential cutover steps"
```

---

## Self-Review Summary

- **Spec coverage:** US-01 → Task 8; US-02 → Task 11 + Task 12 (meal-area event → agent question); US-03 → Task 9 (`record_dose_self_report`) + Task 11 (pillbox → `sensor_supported`); US-04 → Task 5 (risk engine) + Task 9 (`get_current_vitals`) + Task 10 (prompt asks danger symptoms first); US-05 → Task 6 (escalation engine) + Task 12 (notification sidebar). AWS-01 → Task 7. AI-01 → Task 10 (`LLM_PROVIDER`/`LLM_MODEL`/`LLM_API_KEY`). NOTIFY-01 → Task 12 (sidebar only, no real SMS). OCR-01 → out of scope, nothing built. DEVICE-01 → Task 11 (pillbox event is optional; `self_reported` works without it, per Task 9).
- **Placeholder scan:** no TBD/"similar to"/"add error handling" left; every step has runnable code and exact commands.
- **Type consistency:** `Repository` (Task 4) methods match exactly between `InMemoryRepository` (Task 4) and `DynamoDBRepository` (Task 7); `DoseStatus`/`RiskLevel`/`NotificationSeverity` (Task 2) values match every place they're compared (Tasks 5, 6, 9); `build_tools(repo, clock, user_id)` (Task 9) signature matches its call in `build_agent_executor` (Task 10) and `app.py` (Task 12).

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-17-homewellness-mvp.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
