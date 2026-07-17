收到，我先將決策收斂成 SRS v0.2。第 5 點我理解為：**OCR 先不做，完成 MVP 後再評估是否加入**；如果你原意不同再告訴我。

## 已確認的 MVP 決策

| 項目 | 決策 |
|---|---|
| 互動方式 | Streamlit 文字對話，模擬語音 Agent |
| AI 工作流 | Python＋LangChain |
| LLM | 暫定 Gemini API |
| AWS | 至少實際串接一項 AWS 服務 |
| 家屬通知 | 顯示於 Streamlit，不寄送真實簡訊 |
| 藥袋 OCR | MVP 後再評估 |
| Demo 情境 | 頭暈 Tool Calling 與服藥流程合併 |
| 智慧藥盒 | 選配的外接 IoT 裝置 |

## AWS 實作建議

我建議 MVP **實際使用 DynamoDB，Lambda 先列入正式架構，不強制實作**。

理由：

- DynamoDB 可直接證明 Memory 與資料持久化。
- Demo 後重新啟動，仍能查到服藥與事件紀錄。
- Streamlit 可直接展示寫入前後的資料。
- Lambda 在 Live Demo 中較不直觀，增加部署與除錯風險。

MVP 資料流：

```text
IoT 模擬器
    ↓
Streamlit／Python Backend
    ↓
LangChain Agent ──→ Gemini API
    ↓ Tool Calling
DynamoDB
    ├─ 用藥計畫
    ├─ 生理數據
    ├─ 服藥紀錄
    └─ 通知事件
```

正式產品架構則展示：

```text
IoT 裝置
    ↓ MQTT
AWS IoT Core
    ↓
Lambda／EventBridge
    ↓
DynamoDB
    ↓
LangChain Agent Service
    ↓
Gemini API
```

這樣可以清楚區分：

- **PoC 實際做了什麼**
- **正式上線會怎麼擴充**

不要在簡報中讓人誤以為 IoT Core、Lambda、SNS 都已實際部署。

## SRS v0.2 修訂

### UI-01：互動介面

系統應提供 Streamlit 文字對話介面，作為語音 Agent 的互動模擬。

畫面必須標示：

> Text-based simulation of voice interaction

系統不需要執行語音辨識或語音合成。

### AWS-01：資料持久化

系統應實際連接 Amazon DynamoDB，保存：

- 用藥計畫
- 生理數據
- IoT 事件
- 服藥紀錄
- 家屬通知事件
- Agent Session 摘要

若 DynamoDB 無法連線：

- 系統不得假裝寫入成功。
- UI 應顯示資料庫錯誤。
- 對話功能可繼續，但需標示紀錄未持久化。

### AWS-01：真實 DynamoDB

系統必須：
使用 boto3 連接真實 AWS DynamoDB。
讀寫用藥計畫、生理資料、IoT 事件、服藥紀錄及通知。
使用 IAM 最小權限。
從 AWS CLI Profile 或環境變數取得憑證。
禁止將 Access Key 寫入程式碼、.env 範例或 Git。
DynamoDB 無法連線時清楚顯示錯誤，不可假裝寫入成功。
資料表建議
MVP 使用一張表即可：
Table: homewellness-mvp

PK                    SK
USER#user-001         PROFILE
USER#user-001         MEDICATION#med-001
USER#user-001         VITAL#2026-07-17T18:31:00
USER#user-001         IOT_EVENT#2026-07-17T18:30:00#evt-001
USER#user-001         DOSE#2026-07-17#med-001#DINNER
USER#user-001         NOTIFICATION#2026-07-17T19:00:00
USER#user-001         SESSION#session-001
這種設計可用一個使用者 Partition 查詢其相關紀錄，也方便在面試中解釋 DynamoDB 是依「存取模式」設計，而不是照關聯式資料表拆分。
Demo 備援
正式 Demo 預設連接 DynamoDB，但保留：
DATA_BACKEND=dynamodb
DATA_BACKEND=memory
若現場網路或 AWS 驗證失敗，可切換成記憶體模式。畫面必須明確標示目前後端，不能把備援模式說成 AWS 連線成功。
建議實際展示的 DynamoDB 證據
在 Streamlit 側邊顯示：
Backend：AWS DynamoDB
AWS Region
最近一次讀寫時間
最近一次寫入的服藥狀態
Request ID 或事件 ID

### AI-01：模型抽象

系統應透過 LangChain 的模型介面呼叫 Gemini，不得將核心流程綁死在特定模型。

建議保留以下設定：

```text
LLM_PROVIDER
LLM_MODEL
LLM_API_KEY
```

如此可在 Gemini 無法使用時替換其他模型，而不修改業務規則與 Tool 定義。

Gemini 的實際模型名稱與免費額度可能變動，開始實作時再依當時官方資訊確認，不要在 SRS 寫死。

### NOTIFY-01：家屬通知模擬

當規則引擎產生通知時，系統應：

1. 將通知寫入 DynamoDB。
2. 在 Streamlit 家屬通知區顯示。
3. 標示事件時間、原因與嚴重程度。
4. 不實際傳送 SMS、Email 或電話。
5. 不宣稱已聯絡真實家屬或緊急單位。

### OCR-01：OCR 延後

藥袋或處方箋 OCR 不屬於 MVP 驗收範圍。

MVP 使用預先建立且標記為 `confirmed` 的測試用藥計畫。後續若加入 OCR，辨識結果仍須由家屬或授權人員確認後才能啟用。

### DEVICE-01：智慧藥盒定位

智慧藥盒應定義為外接選配裝置，透過統一 IoT 事件格式與系統整合。

主系統不應依賴智慧藥盒才能運作：

- 沒有藥盒：允許 `self_reported`
- 有藥盒事件：允許 `sensor_supported`
- 藥盒離線：維持語音提醒，不得標記為硬體確認

## Demo 最終主線

1. Streamlit 模擬晚餐時段與餐桌停留事件。
2. Agent 主動詢問是否已用餐。
3. 使用者輸入：「吃完了，但今天有點頭暈。」
4. Agent 呼叫 `get_current_vitals()`。
5. Tool 從 DynamoDB 讀取模擬的血壓與心率。
6. 規則引擎進行風險分級。
7. Agent 在安全條件允許時繼續飯後用藥提醒。
8. 模擬外接藥盒開啟及重量下降。
9. 系統寫入 `sensor_supported` 服藥紀錄。
10. Streamlit 顯示更新後的紀錄。

