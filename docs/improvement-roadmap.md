# HomeWellness Companion 補強 Roadmap

本文件依面試作業要求與目前專案狀態，整理後續補強順序。目標是先確保 3–5 分鐘 Live Demo 可穩定完成，再補足 AWS、Memory 與簡報繳交物。

## P0：打通 Live Demo 主線

### 1. 實作 IoT 事件觸發主動對話

目前「模擬：晚餐時段感測事件」只寫入 IoT 事件及執行服藥規則，尚未在聊天區產生 Agent 主動詢問。

完成條件：

- 點擊晚餐感測事件後，聊天區出現主動訊息，例如：「王伯伯，您吃完晚餐了嗎？」
- 訊息必須基於「適合詢問」而非宣稱使用者已用餐。
- 同一事件不可重複觸發多次相同詢問。
- 加入整合測試，驗證 `IoT event → proactive message`。

### 2. 串通完整健康對話流程

完成條件：

- 使用者輸入「吃完了，但今天有點頭暈」後，Agent 先詢問胸痛、呼吸困難等危險警訊。
- 使用者回答後，Agent 呼叫 `get_current_vitals`。
- 回應顯示量測來源、量測時間及規則引擎回傳的風險層級。
- Agent 只使用已確認的用藥計畫提醒服藥。
- 使用者回報已服藥後，系統寫入 `self_reported`。
- 模擬藥盒事件後，狀態更新為 `sensor_supported`。

### 3. 增加穩定的 Demo 備援模式

現場網路、模型 API 或 AWS 可能失敗，因此需要一條不依賴外部服務、但不冒充真實 LLM/AWS 的完整展示路徑。

完成條件：

- UI 清楚標示目前為 `Live LLM`、`Scripted Demo`、`DynamoDB` 或 `Memory`。
- 沒有 LLM Key 時，仍能依預設腳本完成主動關懷與用藥流程。
- 備援模式不宣稱已執行真實 Tool Calling；應清楚標示為模擬結果。
- 準備 Demo 截圖或短錄影作為最終備援。

### 4. 強化 Demo 可觀察性

完成條件：

- 畫面顯示目前服藥狀態、最近生理數據與量測時間。
- 顯示最近 IoT 事件及事件 ID。
- 顯示 Agent 呼叫的 Tool 名稱、輸入與結果摘要。
- 顯示家屬通知的原因、嚴重程度及時間。
- DynamoDB 模式下顯示 Region 與最近一次成功讀寫資訊。

## P1：補足題目指定的技術能力

### 5. 補強 Agent Memory

目前聊天歷史只保存在 Streamlit session 中；用藥與健康資料雖可持久化，但尚未形成跨會話的 Agent 記憶。

完成條件：

- 區分短期對話記憶與長期健康／用藥記憶。
- 儲存 session summary、重要健康事件與最近服藥結果。
- 新 session 可讀取必要摘要，例如近期頭暈紀錄或昨日漏服狀態。
- 避免把完整敏感對話無限制送入模型。
- 加入跨 session 讀寫測試。

### 6. 實際驗證 DynamoDB

完成條件：

- 使用建表腳本建立真實 DynamoDB Table。
- 驗證用藥計畫、生理資料、IoT 事件、服藥紀錄及通知的讀寫。
- 使用 IAM 最小權限，憑證不得提交至 Git。
- 保留 AWS Console 截圖、事件 ID 或 Request ID 作為簡報證據。
- 現場可切換回 Memory backend，且 UI 明確標示。

### 7. 製作正式 AWS 架構圖與 AI 工作流圖

架構圖應清楚區分「PoC 已實作」與「Production Target」，避免讓評審誤以為 IoT Core、Lambda、EventBridge 或 SNS 已部署。

AWS 架構圖至少包含：

- IoT 感測器／智慧藥盒
- MQTT 與 AWS IoT Core
- IoT Rules、Lambda／EventBridge
- DynamoDB
- LangChain Agent Service
- LLM Provider
- 通知服務與家屬端
- 身分驗證、授權、加密與稽核邊界

AI 工作流圖至少包含：

- IoT／時間事件觸發
- 情境判斷
- 主動對話
- Memory 讀取
- Tool Calling
- 規則式風險分流
- 用藥狀態寫入
- 通知與人工介入

## P2：完成面試繳交物

### 8. 製作 15 分鐘簡報

建議控制在 8–10 頁：

1. 問題、目標使用者與核心洞察
2. 產品價值與 MVP 範圍
3. User Journey 與對話 Vibe
4. User Stories／PRD Snippet
5. Live Demo 情境
6. AI Agent 工作流
7. AWS 架構與 PoC／Production 邊界
8. 醫療安全、隱私與風險控制
9. 成功指標、限制與下一步

完成條件：

- 簡報控制在約 10–11 分鐘，保留 3–5 分鐘 Demo。
- 同時輸出 PPT 與 PDF。
- 所有架構與功能宣稱都能對應程式碼或清楚標示為規劃。

### 9. 排演與封裝交付

完成條件：

- 按 `docs/demo-runbook.md` 完整排演至少三次。
- Demo 主線在 3–5 分鐘內完成。
- README 提供安裝、環境變數、啟動、測試及 Demo 步驟。
- 確認 `.env`、AWS Key、API Key 等敏感資訊未進入 Git。
- 整理 GitHub Repo，附上架構圖、Demo 截圖或影片連結。
- 建立現場故障處理清單：LLM、AWS、網路與 UI 問題的切換方式。

## 建議執行順序

```text
主動觸發
  → 完整對話流程
  → Demo 備援與可觀察性
  → Agent Memory
  → DynamoDB 實證
  → AWS／AI 架構圖
  → PPT／PDF
  → 排演與交付檢查
```

原則：在 P0 全部完成以前，不優先增加 OCR、真實語音、更多感測器或新的通知管道。面試評分更重視核心故事是否完整、技術取捨是否清楚，以及 Demo 是否穩定可信。
