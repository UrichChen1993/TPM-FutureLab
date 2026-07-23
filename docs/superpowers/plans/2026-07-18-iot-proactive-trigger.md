# IoT 事件觸發主動對話 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the existing "模擬：晚餐時段感測事件" sidebar button so it produces a proactive chat message asking whether the elder finished dinner, instead of silently writing an IoT event with no chat reaction.

**Architecture:** Add a small pure rule module (`rules/proactive_engine.py`, mirroring the existing `rules/escalation_engine.py` pattern) that maps an `IoTEvent` to a proactive chat message and dedupes by `event_id`. Wire it into `app.py` by extracting the meal-button handler into a plain, session-state-free function (`trigger_meal_event`) so it can be integration-tested without a Streamlit runtime.

**Tech Stack:** Python 3.14, pytest (via `.venv/Scripts/pytest`), Streamlit, existing `domain`/`storage`/`simulator` packages — no new dependencies.

## Global Constraints

- 點擊晚餐感測事件後，聊天區出現主動訊息，例如：「王伯伯，您吃完晚餐了嗎？」
- 訊息必須基於「適合詢問」而非宣稱使用者已用餐。
- 同一事件不可重複觸發多次相同詢問。
- 加入整合測試，驗證 `IoT event → proactive message`。
- Follow existing repo conventions: dataclasses in `domain/models.py`, pure rule functions in `rules/`, tests mirror source module names in `tests/`.

---

## File Structure

- Create `rules/proactive_engine.py` — pure functions that turn an `IoTEvent` into a proactive chat message, with per-event dedup. No Streamlit or repo I/O.
- Create `tests/test_proactive_engine.py` — unit tests for the above.
- Modify `app.py` — change `run_escalation_tick()` to take `(repo, clock, user_id)` instead of reading `st.session_state` directly (needed so the new trigger function is plain and testable); add `trigger_meal_event(repo, clock, user_id, messages, asked_event_ids)`; initialize `st.session_state.proactive_event_ids`; wire the "模擬：晚餐時段感測事件" button to call `trigger_meal_event`.
- Create `tests/test_app_meal_trigger.py` — integration test proving `IoT event → proactive chat message`.

## Task 1: Proactive engine rule module

**Files:**

- Create: `rules/proactive_engine.py`
- Test: `tests/test_proactive_engine.py`

**Interfaces:**

- Consumes: `domain.models.IoTEvent` (existing dataclass with `event_id: str`, `event_type: str` fields).
- Produces:
  - `MEAL_CHECKIN_MESSAGE: str` constant, value `"王伯伯，您吃完晚餐了嗎？"`.
  - `build_proactive_message(event: IoTEvent) -> str | None` — returns `MEAL_CHECKIN_MESSAGE` for `event_type == "MEAL_AREA_PRESENCE"`, else `None`. Later tasks (and `app.py`) call this indirectly through `maybe_trigger_proactive_message`.
  - `maybe_trigger_proactive_message(event: IoTEvent, asked_event_ids: set[str]) -> str | None` — returns the message the first time a given `event.event_id` is seen, mutates `asked_event_ids` by adding that id, and returns `None` on every subsequent call for the same id. This is the function `app.py`'s `trigger_meal_event` (Task 2) calls.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_proactive_engine.py`:

```python
from datetime import datetime

from domain.models import IoTEvent
from rules.proactive_engine import build_proactive_message, maybe_trigger_proactive_message


def make_meal_event(event_id: str = "evt-001") -> IoTEvent:
    return IoTEvent(
        user_id="user-001", event_id=event_id, event_type="MEAL_AREA_PRESENCE",
        occurred_at=datetime(2026, 7, 17, 18, 0), payload={"zone": "dining_table"},
    )


def test_build_proactive_message_for_meal_area_event_asks_a_question():
    message = build_proactive_message(make_meal_event())

    assert message == "王伯伯，您吃完晚餐了嗎？"
    assert "已經吃" not in message  # must ask, not assert the meal already happened


def test_build_proactive_message_returns_none_for_unrelated_event_type():
    event = IoTEvent(
        user_id="user-001", event_id="evt-002", event_type="PILLBOX_OPENED_WEIGHT_DROP",
        occurred_at=datetime(2026, 7, 17, 18, 30), payload={},
    )

    assert build_proactive_message(event) is None


def test_maybe_trigger_proactive_message_fires_once_per_event_id():
    event = make_meal_event()
    asked: set[str] = set()

    first = maybe_trigger_proactive_message(event, asked)
    second = maybe_trigger_proactive_message(event, asked)

    assert first == "王伯伯，您吃完晚餐了嗎？"
    assert second is None
    assert asked == {"evt-001"}


def test_maybe_trigger_proactive_message_fires_independently_for_distinct_events():
    asked: set[str] = set()

    first = maybe_trigger_proactive_message(make_meal_event("evt-001"), asked)
    second = maybe_trigger_proactive_message(make_meal_event("evt-002"), asked)

    assert first == "王伯伯，您吃完晚餐了嗎？"
    assert second == "王伯伯，您吃完晚餐了嗎？"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/pytest tests/test_proactive_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rules.proactive_engine'`

- [ ] **Step 3: Write minimal implementation**

Create `rules/proactive_engine.py`:

```python
from domain.models import IoTEvent

MEAL_CHECKIN_MESSAGE = "王伯伯，您吃完晚餐了嗎？"


def build_proactive_message(event: IoTEvent) -> str | None:
    if event.event_type == "MEAL_AREA_PRESENCE":
        return MEAL_CHECKIN_MESSAGE
    return None


def maybe_trigger_proactive_message(event: IoTEvent, asked_event_ids: set[str]) -> str | None:
    if event.event_id in asked_event_ids:
        return None
    message = build_proactive_message(event)
    if message is not None:
        asked_event_ids.add(event.event_id)
    return message
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/pytest tests/test_proactive_engine.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add rules/proactive_engine.py tests/test_proactive_engine.py
git commit -m "feat: add proactive-message rule for IoT meal-area events"
```

## Task 2: Wire the meal-event trigger into the Streamlit app

**Files:**

- Modify: `app.py:35-60` (the `run_escalation_tick` function and `render_sidebar`'s meal-event button handler), and `app.py:16-32` (`init_state`)
- Test: `tests/test_app_meal_trigger.py`

**Interfaces:**

- Consumes: `rules.proactive_engine.maybe_trigger_proactive_message` (Task 1), `simulator.iot_simulator.simulate_meal_area_event(repo, clock, user_id) -> IoTEvent` (existing), `rules.escalation_engine.ensure_today_doses`/`apply_escalation` (existing).
- Produces: `trigger_meal_event(repo, clock, user_id: str, messages: list[tuple[str, str]], asked_event_ids: set[str]) -> None` — advances `clock` to dinner time, records the IoT event, runs the escalation tick, and appends `("ai", message)` to `messages` when `maybe_trigger_proactive_message` returns a message. This is what `render_sidebar` calls, and what the integration test in this task calls directly.
- Also changes `run_escalation_tick`'s signature from `run_escalation_tick()` to `run_escalation_tick(repo, clock, user_id: str)` — update both remaining call sites in `render_sidebar` ("前進 30 分鐘" and "模擬：藥盒開啟＋重量下降" buttons) to pass `st.session_state.repo, st.session_state.clock, USER_ID`.

- [ ] **Step 1: Write the failing integration test**

Create `tests/test_app_meal_trigger.py`:

```python
from datetime import datetime

from app import trigger_meal_event
from simulator.clock import SimClock
from storage.memory_backend import InMemoryRepository


def test_meal_event_trigger_adds_proactive_chat_message():
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))
    messages: list[tuple[str, str]] = []
    asked_event_ids: set[str] = set()

    trigger_meal_event(repo, clock, "user-001", messages, asked_event_ids)

    assert messages == [("ai", "王伯伯，您吃完晚餐了嗎？")]
    assert len(asked_event_ids) == 1


def test_meal_event_trigger_advances_clock_to_dinner_time():
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 15, 0))

    trigger_meal_event(repo, clock, "user-001", [], set())

    assert clock.now.hour == 18


def test_meal_event_trigger_does_not_duplicate_message_on_repeated_call_with_same_ids():
    repo = InMemoryRepository()
    clock = SimClock.starting_at(datetime(2026, 7, 17, 17, 30))
    messages: list[tuple[str, str]] = []
    asked_event_ids: set[str] = set()

    trigger_meal_event(repo, clock, "user-001", messages, asked_event_ids)
    first_event_id = next(iter(asked_event_ids))
    # Re-simulate the dedup guard directly: a second trigger for an event
    # already in asked_event_ids must not add a second chat message.
    from rules.proactive_engine import maybe_trigger_proactive_message
    from domain.models import IoTEvent

    replay = IoTEvent(
        user_id="user-001", event_id=first_event_id, event_type="MEAL_AREA_PRESENCE",
        occurred_at=clock.now, payload={},
    )
    result = maybe_trigger_proactive_message(replay, asked_event_ids)

    assert result is None
    assert len(messages) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/pytest tests/test_app_meal_trigger.py -v`
Expected: FAIL with `ImportError: cannot import name 'trigger_meal_event' from 'app'`

- [ ] **Step 3: Refactor `run_escalation_tick` and add `trigger_meal_event` in `app.py`**

Replace the existing `run_escalation_tick` function:

```python
def run_escalation_tick() -> None:
    repo, clock = st.session_state.repo, st.session_state.clock
    ensure_today_doses(repo, clock, USER_ID)
    for record in repo.list_dose_records(USER_ID, clock.now.strftime("%Y-%m-%d")):
        apply_escalation(repo, record, clock.now)
```

with:

```python
def run_escalation_tick(repo, clock, user_id: str) -> None:
    ensure_today_doses(repo, clock, user_id)
    for record in repo.list_dose_records(user_id, clock.now.strftime("%Y-%m-%d")):
        apply_escalation(repo, record, clock.now)


def trigger_meal_event(repo, clock, user_id: str, messages: list, asked_event_ids: set) -> None:
    clock.jump_to_dinner()
    event = simulate_meal_area_event(repo, clock, user_id)
    run_escalation_tick(repo, clock, user_id)
    message = maybe_trigger_proactive_message(event, asked_event_ids)
    if message is not None:
        messages.append(("ai", message))
```

Add the import at the top of `app.py`:

```python
from rules.proactive_engine import maybe_trigger_proactive_message
```

- [ ] **Step 4: Initialize `proactive_event_ids` in `init_state` and update `render_sidebar` call sites**

In `init_state`, add after the existing `messages` initialization block:

```python
    if "proactive_event_ids" not in st.session_state:
        st.session_state.proactive_event_ids = set()
```

Replace the three buttons in `render_sidebar`:

```python
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
```

with:

```python
    if st.sidebar.button("模擬：晚餐時段感測事件"):
        trigger_meal_event(
            st.session_state.repo, st.session_state.clock, USER_ID,
            st.session_state.messages, st.session_state.proactive_event_ids,
        )
    if st.sidebar.button("前進 30 分鐘"):
        st.session_state.clock.advance(30)
        run_escalation_tick(st.session_state.repo, st.session_state.clock, USER_ID)
    if st.sidebar.button("模擬：藥盒開啟＋重量下降"):
        simulate_pillbox_event(st.session_state.repo, st.session_state.clock, USER_ID, "med-001", "DINNER")
        run_escalation_tick(st.session_state.repo, st.session_state.clock, USER_ID)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/pytest tests/test_app_meal_trigger.py -v`
Expected: `3 passed`

- [ ] **Step 6: Run the full suite to confirm no regressions**

Run: `.venv/Scripts/pytest -v`
Expected: `40 passed` (33 pre-existing + 4 from Task 1 + 3 from Task 2), `0 failed`.

- [ ] **Step 7: Manually verify in the running app**

Run: `.venv/Scripts/streamlit run app.py`
In the browser: click "模擬：晚餐時段感測事件" in the sidebar. Confirm a chat bubble reading "王伯伯，您吃完晚餐了嗎？" appears in the main chat area. Click the same button again — confirm a second, distinct proactive message is allowed to appear (it is backed by a new IoT event), but note that manually re-invoking `maybe_trigger_proactive_message` for the exact same event id would not.

- [ ] **Step 8: Commit**

```bash
git add app.py tests/test_app_meal_trigger.py
git commit -m "feat: wire IoT meal-area event into a proactive chat message"
```

---

## Self-Review

**1. Spec coverage:**

- "點擊晚餐感測事件後，聊天區出現主動訊息" → Task 2, `trigger_meal_event` appends the message to `messages`, verified in `test_meal_event_trigger_adds_proactive_chat_message`.
- "訊息必須基於「適合詢問」而非宣稱使用者已用餐" → `MEAL_CHECKIN_MESSAGE` is phrased as a question ("...嗎？"); Task 1's `test_build_proactive_message_for_meal_area_event_asks_a_question` asserts it never contains an assertion like "已經吃".
- "同一事件不可重複觸發多次相同詢問" → `maybe_trigger_proactive_message`'s `asked_event_ids` dedup, verified in `test_maybe_trigger_proactive_message_fires_once_per_event_id` and re-exercised at the integration layer in `test_meal_event_trigger_does_not_duplicate_message_on_repeated_call_with_same_ids`.
- "加入整合測試，驗證 IoT event → proactive message" → `tests/test_app_meal_trigger.py` exercises the full path: `simulate_meal_area_event` → `maybe_trigger_proactive_message` → chat `messages` list, with no Streamlit runtime required.

**2. Placeholder scan:** No TBD/TODO markers; every step has runnable code and exact expected pytest output.

**3. Type consistency:** `trigger_meal_event(repo, clock, user_id, messages, asked_event_ids)` in Task 2 matches the signature declared in its own Interfaces block and the calls made in the test file and in `render_sidebar`. `maybe_trigger_proactive_message(event, asked_event_ids)` from Task 1 is used identically in Task 2's `trigger_meal_event` and test. `run_escalation_tick(repo, clock, user_id)`'s new signature is updated at all three call sites inside `render_sidebar` in the same step.

**Note on Step 6's test count:** the full suite total is 33 (existing) + 4 (Task 1) + 3 (Task 2) = 40. The parenthetical in Step 6 is corrected here; when running the plan, expect `40 passed`.
