# 晚餐時段時間觸發主動詢問 — Design

## 背景

目前「主動詢問是否用餐」（`王伯伯，您吃完晚餐了嗎？`）只會在點擊「🍽️ 模擬晚餐時段感測事件」按鈕時觸發（`trigger_meal_event` → `maybe_trigger_proactive_message`，以 IoT `event_id` 去重）。

「⏩ 前進 30 分鐘」按鈕（`app.py:379-381`）只呼叫 `run_escalation_tick`，只會寫入服藥升級用的家屬通知（側邊欄 `st.sidebar.warning`），不會產生任何聊天室主動訊息。也就是說，若 demo 操作者只推進時間、從未點擊感測事件按鈕，系統永遠不會主動詢問用餐狀況——這與 PRD/SRS 對「主動關懷」的描述（進入晚餐時段即應主動詢問）不一致。

PRD.md / SRS.md 目前也只用「預設晚餐時段」這種模糊描述，沒有寫出具體時間範圍，且 PRD 8 節 P0 需求寫的是「時間＋模擬 IoT 事件觸發主動對話」，讀起來像是「兩者都要」，但實際期望的行為是「兩者任一皆可觸發」。

## 目標

1. 補齊 PRD.md / SRS.md，明確寫出晚餐時段為 18:00–19:00，且觸發條件為「時間到達時段」或「感測事件」兩者擇一即可，不需同時發生。
2. 讓「⏩ 前進 30 分鐘」在時鐘首次進入 18:00–19:00 區間時，也能在聊天室產生一次主動詢問訊息，行為與感測事件觸發的訊息一致（同一句話、同樣只是「適合詢問」而非「已判定用餐」）。

## 非目標

- 不統一時間途徑與感測途徑的去重集合（見下方「已知限制」）。
- 不變更服藥升級提醒（`run_escalation_tick` / `apply_escalation`）既有邏輯與側邊欄通知呈現方式。
- 不新增設定介面調整晚餐時段範圍；範圍先寫死為常數。

## 文件變更

### PRD.md

- **US-02 驗收條件**（第 101-106 行附近）：新增一條，明確寫出時間途徑：「系統時間進入 18:00–19:00 晚餐時段、且當日尚未發送用餐詢問時，即使沒有感測事件也會主動詢問。」
- **核心使用者旅程 → 主動關懷**（第 154-159 行）：步驟 1 由「系統進入預設晚餐時段」改為「系統時間進入 18:00–19:00 晚餐時段」，並註明此步驟本身（不需感測器事件）即可觸發步驟 4 的詢問；感測器事件（步驟 2-3）是另一條可各自觸發相同詢問的路徑。
- **8. 功能需求 → P0**（第 213 行）：「時間＋模擬 IoT 事件觸發主動對話」改為「時間或模擬 IoT 事件觸發主動對話（兩者擇一即可觸發，各自獨立去重）」。

### SRS.md

新增一個需求區塊 `PROACTIVE-01：主動用餐詢問觸發條件`（比照現有 `OCR-0x` / `DEVICE-01` 的條列格式），內容涵蓋：

- 晚餐時段定義為 18:00–19:00。
- 觸發途徑二選一，皆可獨立觸發同一句詢問：
  - 系統時間進入晚餐時段，且當日（以系統時鐘所在日期為準）尚未透過「時間途徑」發送過詢問。
  - 居家感測器（模擬）回報餐桌區域停留事件（既有行為，不變）。
- 時間途徑每日最多觸發一次；感測事件途徑依個別事件各自觸發（既有行為，不變）。
- 觸發僅代表「適合詢問」，不等同於「已確認用餐」，措辭需維持疑問句。

`Demo 最終主線` 第 5-6 點維持不動（demo 仍走感測事件路徑），但在該節前加一句備註：時間途徑為背景規則，展示時可用「⏩ 前進 30 分鐘」單獨驗證。

## 程式變更

### `rules/proactive_engine.py`

新增純函式，比照既有 `maybe_trigger_proactive_message` 風格：

```python
from datetime import datetime, time as dt_time

DINNER_WINDOW_START = dt_time(18, 0)
DINNER_WINDOW_END = dt_time(19, 0)


def maybe_trigger_time_based_checkin(now: datetime, asked_dates: set[str]) -> str | None:
    date_key = now.strftime("%Y-%m-%d")
    if date_key in asked_dates:
        return None
    if not (DINNER_WINDOW_START <= now.time() < DINNER_WINDOW_END):
        return None
    asked_dates.add(date_key)
    return MEAL_CHECKIN_MESSAGE
```

- 去重鍵是「日期字串」，不是 IoT `event_id`（此路徑沒有 IoT event）。
- 區間為左閉右開 `[18:00, 19:00)`，與 `escalation_engine.SLOT_TIMES["DINNER"] = time(18, 0)` 的起點一致。

### `app.py`

- 新增 `trigger_time_advance(repo, clock, user_id, messages, asked_dates)`，取代「⏩ 前進 30 分鐘」按鈕目前的行內邏輯：

```python
def trigger_time_advance(repo, clock, user_id: str, messages: list, asked_dates: set) -> None:
    clock.advance(30)
    run_escalation_tick(repo, clock, user_id)
    message = maybe_trigger_time_based_checkin(clock.now, asked_dates)
    if message is not None:
        messages.append(("ai", message))
```

- `init_state()` 新增 `st.session_state.proactive_time_checkin_dates: set[str]`（獨立於既有的 `proactive_event_ids`）。
- 按鈕 handler 改為呼叫 `trigger_time_advance(st.session_state.repo, st.session_state.clock, USER_ID, st.session_state.messages, st.session_state.proactive_time_checkin_dates)`。
- import `maybe_trigger_time_based_checkin`。

### 已知限制（刻意不處理）

時間途徑（`proactive_time_checkin_dates`，以日期去重）與感測途徑（`proactive_event_ids`，以 event id 去重）是兩個獨立集合。若操作者在同一個晚餐時段內，先讓時間途徑觸發、又手動點擊感測事件按鈕，會收到兩則相同的詢問訊息。這在目前 demo 操作模式下發生機率低，暫不合併去重集合；若未來需要，作法是讓 `trigger_meal_event` 也把當日日期寫進 `proactive_time_checkin_dates`（或反向），一行程式碼可解決。

## 測試

- `tests/test_proactive_engine.py`：新增 `maybe_trigger_time_based_checkin` 的單元測試 — 區間內首次觸發、區間內第二次不觸發（同日）、區間外（17:59 / 19:00 整）不觸發、跨日後可再次觸發。
- `tests/test_app_meal_trigger.py`（或新檔 `tests/test_app_time_trigger.py`）：整合測試 `trigger_time_advance` — 從 17:30 起點連續呼叫兩次（30 分鐘×2 = 18:30，落在區間內)產生一則聊天訊息且只有一則；從區間外時間（如 20:00）呼叫不產生訊息。

## Self-Review

- **佔位符掃描**：無 TBD/TODO，所有變更點都給出具體檔案位置與程式碼。
- **一致性**：`DINNER_WINDOW_START = time(18, 0)` 與 SRS 既有 `escalation_engine.SLOT_TIMES["DINNER"]` 一致；PRD/SRS 措辭都改為「兩者擇一」，不再互相矛盾。
- **範圍**：僅涉及 `rules/proactive_engine.py`、`app.py`、對應測試與 PRD.md/SRS.md 兩份文件，不擴及升級提醒或家屬通知邏輯，範圍收斂，可交給單一 implementation plan。
- **模糊點澄清**：區間邊界明訂為 `[18:00, 19:00)`（19:00 整不算在內），避免「18-19點之間」的口語模糊被誤讀成閉區間。
