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
