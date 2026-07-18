# HomeWellness Companion (MVP)

主動式健康關懷與用藥提醒系統。以 Streamlit 文字對話模擬語音 Agent，結合 LangChain + Gemini 與時間／IoT 事件，在適當情境主動關懷長者、確認用餐與服藥狀態；風險分級與提醒升級由規則引擎決定，LLM 不自行制定醫療規則。

完整需求見 [PRD.md](PRD.md)、[SRS.md](SRS.md)；實作計畫見 [docs/superpowers/plans/2026-07-17-homewellness-mvp.md](docs/superpowers/plans/2026-07-17-homewellness-mvp.md)；Live Demo 步驟見 [docs/demo-runbook.md](docs/demo-runbook.md)。

## 現況

- **AWS / Gemini 憑證尚未備妥** — 開發模式使用 `DATA_BACKEND=memory`，對話面板會顯示「LLM 尚未設定」，但側欄的情境模擬按鈕（晚餐事件、前進時間、藥盒事件）可完整測試服藥提醒、升級與家屬通知流程，不需要 LLM。
- 33 個 pytest 測試涵蓋規則引擎、儲存層、Agent 工具與 Streamlit 進入點。

## 架構

```
domain/     狀態列舉與資料模型（MealStatus、DoseStatus、RiskLevel、MedicationPlan...）
storage/    Repository 介面 + InMemoryRepository / DynamoDBRepository（DATA_BACKEND 切換）
rules/      純規則引擎：risk_engine（生理數據風險分級）、escalation_engine（服藥提醒升級）
simulator/  SimClock（可控制的模擬時鐘）、iot_simulator（模擬餐桌感測／藥盒事件）
agent/      LangChain 工具（agent/tools.py）+ Gemini 模型 + Agent 組裝（create_agent）
app.py      Streamlit 進入點：對話介面、側欄狀態、情境模擬按鈕、家屬通知
seed_data.py 預先載入的測試用藥計畫（US-01）
```

依賴方向單向：`domain → storage → rules → simulator → agent → app.py`。LLM 只透過 `agent/tools.py` 呼叫規則引擎與儲存層，不直接判斷風險或存取未確認的用藥資料。

## 安裝與執行

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt

cp .env.example .env   # 開發模式預設值即可直接執行，無需修改
.venv/Scripts/streamlit run app.py
```

啟動後側欄可看到 `Backend：memory`；用左側「模擬：晚餐時段感測事件」「前進 30 分鐘」「模擬：藥盒開啟＋重量下降」按鈕即可走完服藥提醒、逾時升級與家屬通知的完整流程。

## 測試

```bash
.venv/Scripts/pytest -v
```

## 切換到真實 AWS / Gemini

1. 設定 AWS 憑證（CLI profile 或環境變數），執行一次：
   ```bash
   .venv/Scripts/python scripts/create_dynamodb_table.py
   ```
2. 在 `.env` 設定 `DATA_BACKEND=dynamodb`、`LLM_API_KEY=<gemini key>`。
3. 重新啟動 `streamlit run app.py`，側欄應顯示 `Backend：dynamodb` 與正確的 Region。

詳細步驟與 Live Demo 腳本見 [docs/demo-runbook.md](docs/demo-runbook.md)。

## 環境變數（`.env`）

| 變數 | 預設值 | 說明 |
|---|---|---|
| `DATA_BACKEND` | `memory` | `memory` 或 `dynamodb` |
| `AWS_REGION` | `ap-northeast-1` | DynamoDB 所在區域 |
| `DYNAMODB_TABLE` | `homewellness-mvp` | 單表設計，PK=`USER#{user_id}` |
| `LLM_PROVIDER` | `google_genai` | 目前僅支援 Gemini |
| `LLM_MODEL` | `gemini-1.5-flash` | Gemini 模型名稱 |
| `LLM_API_KEY` | 空 | 未設定時對話面板顯示「LLM 尚未設定」，模擬按鈕仍可用 |

## 安全與規則設計

- 風險分級（血壓/心率閾值）與服藥提醒升級時間（20/20/60/120 分鐘）皆為 MVP 預設值，定義於 [rules/config.py](rules/config.py)，可獨立調整不影響其他程式碼。
- `get_current_vitals` 工具會將使用者確認的危險警訊（如胸痛、呼吸困難）與生理數據一併交給 `rules/risk_engine.py` 的 `combine_risk` 判斷，風險等級不由 LLM 自行決定。
- `get_medication_plan` 僅回傳 `confirmed=True` 的用藥計畫。
- DynamoDB 寫入失敗會直接拋出例外並顯示於畫面，不會假裝寫入成功。
