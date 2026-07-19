# 晚餐時段時間觸發主動詢問 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the "⏩ 前進 30 分鐘" sidebar button also fire the proactive dinner check-in message (`王伯伯，您吃完晚餐了嗎？`) the first time the simulated clock enters the 18:00–19:00 window, independent of the existing IoT-sensor-triggered path — and update PRD.md/SRS.md so they describe this as two independent trigger conditions instead of implying both are required.

**Architecture:** Add a second pure function to `rules/proactive_engine.py` (`maybe_trigger_time_based_checkin`), deduped by calendar date instead of IoT `event_id` since this path has no IoT event. Extract the "⏩ 前進 30 分鐘" button's inline logic into a plain, testable `trigger_time_advance` function in `app.py`, mirroring the existing `trigger_meal_event` pattern. A new, independent session-state set (`proactive_time_checkin_dates`) tracks the time-path dedup, separate from the existing `proactive_event_ids` used by the sensor path.

**Tech Stack:** Python 3.14, pytest (via `.venv/Scripts/pytest`), Streamlit — no new dependencies.

## Global Constraints

- 晚餐時段固定為 18:00–19:00，左閉右開：`18:00 <= now.time() < 19:00`。
- 時間途徑與感測途徑各自獨立觸發同一句訊息「王伯伯，您吃完晚餐了嗎？」，兩者擇一即可，不需同時發生。
- 時間途徑以「日期字串」去重，每日最多觸發一次；感測途徑維持既有以 `event_id` 去重的行為，不變更。
- 兩條途徑的去重集合刻意不合併（見 spec「已知限制」），不在本計畫範圍內處理。
- Follow existing repo conventions: pure rule functions in `rules/`, plain testable functions in `app.py`, tests mirror source module names in `tests/`.

Spec: `docs/superpowers/specs/2026-07-19-dinner-window-proactive-trigger-design.md`

---

## File Structure

- Modify `rules/proactive_engine.py` — add `DINNER_WINDOW_START`, `DINNER_WINDOW_END`, `maybe_trigger_time_based_checkin`.
- Modify `tests/test_proactive_engine.py` — add unit tests for the new function.
- Modify `app.py` — add `trigger_time_advance`; add `proactive_time_checkin_dates` to `init_state`; rewire the "⏩ 前進 30 分鐘" button.
- Create `tests/test_app_time_trigger.py` — integration tests for `trigger_time_advance`.
- Modify `PRD.md` — US-02 acceptance criteria, 主動關懷 journey step 1, P0 list.
- Modify `SRS.md` — new `PROACTIVE-01` requirement block, one-line note before `Demo 最終主線`.

## Task 1: Time-based check-in rule function

**Files:**

- Modify: `rules/proactive_engine.py`
- Test: `tests/test_proactive_engine.py`

**Interfaces:**

- Consumes: nothing new (uses stdlib `datetime`/`time`).
- Produces: `DINNER_WINDOW_START: time`, `DINNER_WINDOW_END: time`, `maybe_trigger_time_based_checkin(now: datetime, asked_dates: set[str]) -> str | None` — returns `MEAL_CHECKIN_MESSAGE` the first time `now.time()` falls in `[DINNER_WINDOW_START, DINNER_WINDOW_END)` for a given calendar date (`now.strftime("%Y-%m-%d")`), mutates `asked_dates` by adding that date string, and returns `None` outside the window or if that date is already in `asked_dates`. This is the function `app.py`'s `trigger_time_advance` (Task 2) calls.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_proactive_engine.py`:

```python
def test_maybe_trigger_time_based_checkin_fires_on_window_start():
    now = datetime(2026, 7, 17, 18, 0)
    asked_dates: set[str] = set()

    message = maybe_trigger_time_based_checkin(now, asked_dates)

    assert message == "王伯伯，您吃完晚餐了嗎？"
    assert asked_dates == {"2026-07-17"}


def test_maybe_trigger_time_based_checkin_does_not_repeat_same_day():
    asked_dates: set[str] = set()
    maybe_trigger_time_based_checkin(datetime(2026, 7, 17, 18, 0), asked_dates)

    second = maybe_trigger_time_based_checkin(datetime(2026, 7, 17, 18, 30), asked_dates)

    assert second is None
    assert asked_dates == {"2026-07-17"}


def test_maybe_trigger_time_based_checkin_ignores_time_before_window():
    message = maybe_trigger_time_based_checkin(datetime(2026, 7, 17, 17, 59), set())

    assert message is None


def test_maybe_trigger_time_based_checkin_ignores_time_at_or_after_window_end():
    message = maybe_trigger_time_based_checkin(datetime(2026, 7, 17, 19, 0), set())

    assert message is None


def test_maybe_trigger_time_based_checkin_fires_again_on_a_new_day():
    asked_dates = {"2026-07-17"}

    message = maybe_trigger_time_based_checkin(datetime(2026, 7, 18, 18, 0), asked_dates)

    assert message == "王伯伯，您吃完晚餐了嗎？"
    assert asked_dates == {"2026-07-17", "2026-07-18"}
```

Update the import line at the top of `tests/test_proactive_engine.py` from:

```python
from rules.proactive_engine import build_proactive_message, maybe_trigger_proactive_message
```

to:

```python
from rules.proactive_engine import (
    build_proactive_message,
    maybe_trigger_proactive_message,
    maybe_trigger_time_based_checkin,
)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/pytest tests/test_proactive_engine.py -v`
Expected: FAIL with `ImportError: cannot import name 'maybe_trigger_time_based_checkin' from 'rules.proactive_engine'`

- [ ] **Step 3: Write minimal implementation**

In `rules/proactive_engine.py`, change the import line from:

```python
from domain.models import IoTEvent, MedicationPlan
```

to:

```python
from datetime import datetime, time as dt_time

from domain.models import IoTEvent, MedicationPlan

DINNER_WINDOW_START = dt_time(18, 0)
DINNER_WINDOW_END = dt_time(19, 0)
```

Then append this function at the end of `rules/proactive_engine.py`:

```python
def maybe_trigger_time_based_checkin(now: datetime, asked_dates: set[str]) -> str | None:
    date_key = now.strftime("%Y-%m-%d")
    if date_key in asked_dates:
        return None
    if not (DINNER_WINDOW_START <= now.time() < DINNER_WINDOW_END):
        return None
    asked_dates.add(date_key)
    return MEAL_CHECKIN_MESSAGE
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/pytest tests/test_proactive_engine.py -v`
Expected: all tests in the file pass (existing ones + 5 new ones).

- [ ] **Step 5: Commit**

```bash
git add rules/proactive_engine.py tests/test_proactive_engine.py
git commit -m "feat: add time-window trigger for the dinner check-in message"
```

## Task 2: Wire the time-based trigger into the Streamlit app

**Files:**

- Modify: `app.py:8` (import), `app.py:52-71` (`init_state`), `app.py:74-88` (add `trigger_time_advance` after `run_escalation_tick`), `app.py:379-381` (button handler)
- Test: `tests/test_app_time_trigger.py` (new file)

**Interfaces:**

- Consumes: `rules.proactive_engine.maybe_trigger_time_based_checkin` (Task 1), existing `run_escalation_tick(repo, clock, user_id: str) -> None`.
- Produces: `trigger_time_advance(repo, clock, user_id: str, messages: list, asked_dates: set) -> None` — advances `clock` by 30 minutes, runs the escalation tick, and appends `("ai", message)` to `messages` when `maybe_trigger_time_based_checkin` returns a message. This is what `render_sidebar`'s "⏩ 前進 30 分鐘" button calls.

- [ ] **Step 1: Write the failing integration tests**

Create `tests/test_app_time_trigger.py`:

```python
from datetime import datetime

from app import trigger_time_advance
from simulator.clock import SimClock
from storage.memory_backend import InMemoryRepository


def test_time_advance_fires_checkin_on_first_entry_into_dinner_window():
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))
    messages: list[tuple[str, str]] = []
    asked_dates: set[str] = set()

    trigger_time_advance(repo, clock, "user-001", messages, asked_dates)

    assert clock.now == datetime(2026, 7, 17, 18, 0)
    assert messages == [("ai", "王伯伯，您吃完晚餐了嗎？")]
    assert asked_dates == {"2026-07-17"}


def test_time_advance_does_not_repeat_checkin_same_day():
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))
    messages: list[tuple[str, str]] = []
    asked_dates: set[str] = set()

    trigger_time_advance(repo, clock, "user-001", messages, asked_dates)
    trigger_time_advance(repo, clock, "user-001", messages, asked_dates)

    assert clock.now == datetime(2026, 7, 17, 18, 30)
    assert len(messages) == 1


def test_time_advance_outside_window_adds_no_message():
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 19, 30))
    messages: list[tuple[str, str]] = []
    asked_dates: set[str] = set()

    trigger_time_advance(repo, clock, "user-001", messages, asked_dates)

    assert messages == []
    assert asked_dates == set()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/pytest tests/test_app_time_trigger.py -v`
Expected: FAIL with `ImportError: cannot import name 'trigger_time_advance' from 'app'`

- [ ] **Step 3: Add the import**

In `app.py`, change line 8 from:

```python
from rules.proactive_engine import maybe_trigger_proactive_message
```

to:

```python
from rules.proactive_engine import (
    maybe_trigger_proactive_message,
    maybe_trigger_time_based_checkin,
)
```

- [ ] **Step 4: Add session-state init**

In `init_state` (`app.py:52-71`), change:

```python
    if "proactive_event_ids" not in st.session_state:
        st.session_state.proactive_event_ids = set()
```

to:

```python
    if "proactive_event_ids" not in st.session_state:
        st.session_state.proactive_event_ids = set()
    if "proactive_time_checkin_dates" not in st.session_state:
        st.session_state.proactive_time_checkin_dates = set()
```

- [ ] **Step 5: Add `trigger_time_advance`**

In `app.py`, right after the existing `trigger_meal_event` function (`app.py:80-88`), add:

```python
def trigger_time_advance(repo, clock, user_id: str, messages: list, asked_dates: set) -> None:
    clock.advance(30)
    run_escalation_tick(repo, clock, user_id)
    message = maybe_trigger_time_based_checkin(clock.now, asked_dates)
    if message is not None:
        messages.append(("ai", message))
```

- [ ] **Step 6: Rewire the button handler**

In `render_sidebar` (`app.py:379-381`), change:

```python
    if st.sidebar.button("⏩ 前進 30 分鐘", use_container_width=True):
        st.session_state.clock.advance(30)
        run_escalation_tick(st.session_state.repo, st.session_state.clock, USER_ID)
```

to:

```python
    if st.sidebar.button("⏩ 前進 30 分鐘", use_container_width=True):
        trigger_time_advance(
            st.session_state.repo, st.session_state.clock, USER_ID,
            st.session_state.messages, st.session_state.proactive_time_checkin_dates,
        )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/Scripts/pytest tests/test_app_time_trigger.py -v`
Expected: `3 passed`

- [ ] **Step 8: Run the full suite to confirm no regressions**

Run: `.venv/Scripts/pytest -v`
Expected: all tests pass, `0 failed`.

- [ ] **Step 9: Manually verify in the running app**

Run: `.venv/Scripts/streamlit run app.py`
In the browser, without touching "🍽️ 模擬晚餐時段感測事件", click "⏩ 前進 30 分鐘" repeatedly starting from the default 17:30 clock. Confirm a chat bubble reading "王伯伯，您吃完晚餐了嗎？" appears exactly once, the first time the clock reaches 18:00, and does not reappear on subsequent clicks that stay within 18:00–19:00.

- [ ] **Step 10: Commit**

```bash
git add app.py tests/test_app_time_trigger.py
git commit -m "feat: fire dinner check-in when the sim clock enters the dinner window"
```

## Task 3: Update PRD.md and SRS.md

**Files:**

- Modify: `PRD.md:103` (US-02 acceptance criteria), `PRD.md:156` (主動關懷 journey step 1), `PRD.md:213` (P0 functional list)
- Modify: `SRS.md:229-237` (insert new `PROACTIVE-01` block after `DEVICE-01`), `SRS.md:239` (note before `Demo 最終主線`)

No automated test — this is documentation only. Verification is a manual read-through in Step 3 below.

- [ ] **Step 1: Update PRD.md**

In `PRD.md`, change (`PRD.md:101-106`):

```markdown
驗收條件：

- 系統根據用餐時段及模擬 IoT 事件觸發詢問。
- IoT 訊號只觸發對話，不直接判定使用者已用餐。
- 使用者回答「還沒吃」時，可延後提醒。
- 使用者回答不明確時，Agent 應再次簡短確認。
```

to:

```markdown
驗收條件：

- 系統時間進入 18:00–19:00 晚餐時段、或收到模擬 IoT 事件時，皆會主動觸發詢問（兩者擇一即可，不需同時發生）。
- 時間途徑每日僅觸發一次；IoT 事件途徑依個別事件各自觸發。
- IoT 訊號只觸發對話，不直接判定使用者已用餐。
- 使用者回答「還沒吃」時，可延後提醒。
- 使用者回答不明確時，Agent 應再次簡短確認。
```

Change (`PRD.md:154-159`):

```markdown
### 主動關懷

1. 系統進入預設晚餐時段。
2. 居家感測器回報餐桌區域停留事件。
3. 系統判定「適合詢問」，而非「確定已用餐」。
4. Agent 主動詢問：「王伯伯，您吃完晚餐了嗎？」
```

to:

```markdown
### 主動關懷

1. 系統時間進入 18:00–19:00 晚餐時段（此步驟本身即可直接觸發步驟 4 的詢問）。
2. 居家感測器回報餐桌區域停留事件（另一條可獨立觸發相同詢問的路徑）。
3. 系統判定「適合詢問」，而非「確定已用餐」。
4. Agent 主動詢問：「王伯伯，您吃完晚餐了嗎？」
```

Change (`PRD.md:213`):

```markdown
- 時間＋模擬 IoT 事件觸發主動對話
```

to:

```markdown
- 時間或模擬 IoT 事件觸發主動對話（兩者擇一即可，各自獨立觸發與去重）
```

- [ ] **Step 2: Update SRS.md**

In `SRS.md`, after the `DEVICE-01` block and before `## Demo 最終主線` (`SRS.md:229-239`), which currently reads:

```markdown
### DEVICE-01：智慧藥盒定位

智慧藥盒應定義為外接選配裝置，透過統一 IoT 事件格式與系統整合。

主系統不應依賴智慧藥盒才能運作：

- 沒有藥盒：允許 `self_reported`
- 有藥盒事件：允許 `sensor_supported`
- 藥盒離線：維持語音提醒，不得標記為硬體確認

## Demo 最終主線
```

insert a new requirement block and a note, producing:

```markdown
### DEVICE-01：智慧藥盒定位

智慧藥盒應定義為外接選配裝置，透過統一 IoT 事件格式與系統整合。

主系統不應依賴智慧藥盒才能運作：

- 沒有藥盒：允許 `self_reported`
- 有藥盒事件：允許 `sensor_supported`
- 藥盒離線：維持語音提醒，不得標記為硬體確認

### PROACTIVE-01：主動用餐詢問觸發條件

- 晚餐時段定義為 18:00–19:00（左閉右開）。
- 觸發途徑二選一，皆可獨立觸發同一句「王伯伯，您吃完晚餐了嗎？」：
  - 系統時間進入晚餐時段，且當日尚未透過「時間途徑」發送過詢問。
  - 居家感測器（模擬）回報餐桌區域停留事件。
- 時間途徑每日最多觸發一次；IoT 事件途徑依個別事件各自觸發，不做每日次數限制。
- 觸發僅代表「適合詢問」，不得視為已確認用餐，措辭需維持疑問句。

## Demo 最終主線

> 主動用餐詢問的時間途徑（PROACTIVE-01）為背景規則，不在下列主線內獨立列出；可於 Streamlit 側邊欄使用「⏩ 前進 30 分鐘」單獨驗證。
```

- [ ] **Step 3: Manual read-through**

Open `PRD.md` and `SRS.md` and confirm: (a) no leftover mention of "時間＋" (AND-wording) for this trigger anywhere in either file, (b) the 18:00–19:00 window is stated identically in both files, (c) `PROACTIVE-01` reads consistently with `rules/proactive_engine.py`'s `DINNER_WINDOW_START`/`DINNER_WINDOW_END` from Task 1.

- [ ] **Step 4: Commit**

```bash
git add PRD.md SRS.md
git commit -m "docs: describe dinner check-in as time-or-sensor triggered, not time-and-sensor"
```

---

## Self-Review

**1. Spec coverage:**

- "PRD.md / SRS.md 補齊 18:00–19:00 與時間或觸發的措辭" → Task 3.
- "時鐘首次進入 18:00–19:00 觸發一次主動詢問" → Task 1 (`maybe_trigger_time_based_checkin`) + Task 2 (`trigger_time_advance`, integration tests).
- "同一句訊息，不新增文案分支" → Task 1 directly returns the existing `MEAL_CHECKIN_MESSAGE` constant, no new string.
- "去重鍵為日期而非 event_id，且與既有感測途徑去重集合分開" → Task 1 uses `now.strftime("%Y-%m-%d")` keys; Task 2 introduces a separate `proactive_time_checkin_dates` session-state set, distinct from `proactive_event_ids`.
- "已知限制：兩去重集合不合併" → intentionally not a task; called out in Global Constraints so no implementer accidentally "fixes" it mid-plan.

**2. Placeholder scan:** No TBD/TODO; every step has runnable code, exact before/after text, and exact expected command output.

**3. Type consistency:** `maybe_trigger_time_based_checkin(now: datetime, asked_dates: set[str]) -> str | None` (Task 1) is called identically in `trigger_time_advance(repo, clock, user_id: str, messages: list, asked_dates: set) -> None` (Task 2) as `maybe_trigger_time_based_checkin(clock.now, asked_dates)`. `trigger_time_advance`'s parameter order/names mirror the existing `trigger_meal_event(repo, clock, user_id, messages, asked_event_ids)` for consistency. The button handler in Task 2 Step 6 passes `st.session_state.proactive_time_checkin_dates`, which is the exact name initialized in Task 2 Step 4.
