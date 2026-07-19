# Demo Runbook

## 開發模式（目前，無 AWS / Gemini 憑證）

1. `DATA_BACKEND=memory`，`.env` 中 `LLM_API_KEY` 留空。
2. `streamlit run app.py`。
3. 側欄會顯示 `Backend：memory`；對話區則會顯示「LLM 尚未設定」提示。此時無法測試對話，
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

1. 選擇「示範藥單」、「相機拍攝」或「上傳圖片」，點擊「執行模擬 OCR」→ 顯示藥名、每次劑量、頻率、服用時機、有效期間、信心值及可信來源的藥品外觀參考。
2. 展開「校對」修正欄位；可切換成固定時間以展示具體時間要求，也可用「手動新增藥物」及刪除按鈕展示 OCR 失敗時的替代流程。
3. 若留下必填欄位空白，畫面會列出缺少欄位且不允許確認。資料完整後，逐筆點擊「確認此筆必要資料」。
4. 所有候選完成核對後，點擊「啟用已確認用藥計畫」；側欄會顯示有效計畫及建立、核對、啟用稽核紀錄。
5. 點擊「模擬晚餐時段感測事件」→ Agent 主動詢問是否已用餐，並說明飯後應服用「脈優錠 5mg 1顆（每日1次）」。
6. 在對話框輸入：「吃完了，但今天有點頭暈。」
7. Agent 應先詢問是否有胸痛、呼吸困難等危險警訊，再呼叫
   `get_current_vitals`，並說明資料來源與量測時間。
8. 使用者回報「吃藥了」→ Agent 呼叫 `record_dose_self_report`，僅記錄口頭回報。
9. 點擊「模擬藥盒開啟＋重量下降」→ 服藥紀錄升級為 `sensor_supported`；說明應使用「感測訊號支持已完成」，不得宣稱已證明吞服。
10. 側欄顯示更新後的服藥狀態與（如有觸發）家屬通知。

## 驗證未回應情境

1. 點擊「模擬：晚餐時段感測事件」後不輸入任何訊息。
2. 連續點擊「前進 30 分鐘」：
   - 第 1 次（due+20~30 分）→ 狀態變 `reminded`。
   - 第 2 次（due+60 分）→ 狀態變 `missed`，側欄出現 medium 通知。
   - 第 4 次（due+120 分）→ 側欄出現 high 通知（長時間無回應升級）。
