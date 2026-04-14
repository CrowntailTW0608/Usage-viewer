# Plan: GAI Usage Viewer - Windows Desktop App

## TL;DR
建立一個 PyQt6 Windows 桌面應用，即時顯示多家 GAI 服務的使用量（Token、歷史趨勢、速率限制）。先支援 Claude 和 Gemini，架構設計為插件式以便未來擴展 OpenAI 和 GitHub Copilot。

## 研究發現

### 各家 API 用量取得方式

| 服務 | 用量 API | 認證方式 | 備註 |
|------|----------|----------|------|
| Claude (Anthropic) | `/v1/organizations/usage_report/messages` + `/v1/organizations/cost_report` | Admin API Key (`sk-ant-admin...`) | 一般 API Key 無法存取用量。需 Admin Key |
| Gemini (AI Studio) | **無直接用量查詢 API** | - | 只有 Web 儀表板。可透過 response `usage_metadata` 本地追蹤 |
| OpenAI | `/v1/organization/usage/completions` | Admin API Key | 完整的用量 API，含 token 和成本 |
| GitHub Copilot | `/users/{username}/settings/billing/premium_request/usage` | PAT (需 Plan 權限) | API 版本 `2026-03-10` |

### 關鍵限制
- **Claude**: 需要 Admin Key，一般 Key 完全無法查詢用量
- **Gemini**: 官方無用量查詢 API，只能本地追蹤或讀 Web Dashboard
- **OpenAI**: 需要組織管理員 Key
- **GitHub Copilot**: 需要 PAT + Plan 權限

---

## 架構設計

```
d:\pyData\Usage viewer\
├── main.py                    # 應用入口
├── requirements.txt           # 依賴
├── config.json                # 使用者設定（加密 key 存儲）
│
├── app/
│   ├── __init__.py
│   ├── main_window.py         # 主視窗 (PyQt6)
│   ├── settings_dialog.py     # 設定對話框（新增/管理 Provider）
│   ├── widgets/
│   │   ├── __init__.py
│   │   ├── provider_card.py   # 單一 Provider 的顯示卡片 Widget
│   │   ├── usage_chart.py     # 歷史趨勢圖表 Widget (QChart)
│   │   └── status_bar.py      # 底部狀態列
│   │
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py            # BaseProvider 抽象類別
│   │   ├── claude.py          # Claude Admin API 用量取得
│   │   ├── gemini.py          # Gemini（本地追蹤 + dashboard scraping）
│   │   ├── openai_provider.py # OpenAI 用量 API（未來）
│   │   └── copilot.py         # GitHub Copilot 用量（未來）
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── poller.py          # 背景輪詢管理（QThread/QTimer）
│   │   ├── config_manager.py  # 設定讀寫（含 API Key 加密）
│   │   └── data_store.py      # SQLite 本地歷史儲存
│   │
│   └── resources/
│       ├── icons/             # Provider 圖示
│       └── styles.qss         # Qt 樣式表
```

---

## 實作步驟

### Phase 1: 核心框架 (Steps 1-4)

**Step 1: 專案初始化**
- 建立目錄結構和 `requirements.txt`
- 依賴: `PyQt6`, `PyQt6-Charts`, `requests`, `cryptography`, `keyring`
- 建立 `main.py` 入口

**Step 2: 設定管理 (`config_manager.py`)**
- 用 `keyring` 儲存 API Key（利用 Windows Credential Manager）
- `config.json` 儲存非敏感設定（啟用的 Provider 列表、輪詢間隔、UI 偏好）
- 設定結構:
  ```
  {
    "providers": [
      {"type": "claude", "enabled": true, "label": "Claude (工作)", "poll_interval": 300},
      {"type": "gemini", "enabled": true, "label": "Gemini", "poll_interval": 300}
    ],
    "ui": {"theme": "dark", "refresh_interval": 300}
  }
  ```

**Step 3: Provider 抽象層 (`base.py`)**
- `BaseProvider` ABC 定義統一介面:
  - `fetch_usage(start: datetime, end: datetime) -> UsageData`
  - `get_rate_limits() -> RateLimits | None`
  - `test_connection() -> bool`
  - `provider_name: str`, `provider_icon: str`
- `UsageData` dataclass: `input_tokens`, `output_tokens`, `cached_tokens`, `cost_usd`, `period`, `model_breakdown`
- `RateLimits` dataclass: `rpm`, `tpm`, `rpd`

**Step 4: 本地資料儲存 (`data_store.py`)**
- SQLite 資料庫存歷史用量資料
- 表: `usage_records(provider, timestamp, input_tokens, output_tokens, cached_tokens, cost_usd, model, raw_json)`
- 支援查詢: 日/週/月彙總

### Phase 2: Provider 實作 (Steps 5-6, 可平行)

**Step 5: Claude Provider (`claude.py`)** *parallel with Step 6*
- 使用 Anthropic Admin API:
  - `GET /v1/organizations/usage_report/messages` (token 用量)
  - `GET /v1/organizations/cost_report` (USD 成本)
- Headers: `x-api-key`, `anthropic-version: 2023-06-01`
- 查詢參數: `starting_at`, `ending_at`, `bucket_width` (1d/1h)
- 解析回應中的 `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`
- 錯誤處理: 401 (key 無效)、403 (非 admin key)、429 (rate limit)

**Step 6: Gemini Provider (`gemini.py`)** *parallel with Step 5*
- **方案 A (主要)**: 無官方用量 API → 本地追蹤模式
  - 讀取使用者手動輸入的 token bucket 資訊
  - 顯示已知的 rate limits (RPM/TPM/RPD) 基於 tier
- **方案 B (備選)**: 若使用者有 Google Cloud 專案
  - 用 Cloud Monitoring API 查詢 Vertex AI 用量
- 初版先顯示 rate limit 資訊 + 手動/本地追蹤的 token 統計

### Phase 3: UI 實作 (Steps 7-9)

**Step 7: 主視窗 (`main_window.py`)** *depends on Steps 3, 4*
- PyQt6 QMainWindow
- 上方: 工具列 (設定按鈕、手動刷新、時間範圍選擇)
- 中央: QScrollArea 含多個 ProviderCard (垂直排列或 Grid)
- 下方: 狀態列 (最後更新時間、下次更新倒數)
- 系統托盤圖示 (最小化到工作列)

**Step 8: Provider 卡片 Widget (`provider_card.py`)** *depends on Step 3*
- 每個 Provider 一張卡片，顯示:
  - Provider 名稱 + 圖示 + 連線狀態 (綠/紅燈)
  - Token 用量: 輸入/輸出/快取 (數字 + 進度條)
  - 歷史趨勢圖表 (嵌入式 QChart，7天/30天)
  - Rate Limits: RPM/TPM 目前值 vs 上限
- 卡片可展開/收合

**Step 9: 設定對話框 (`settings_dialog.py`)** *depends on Step 2*
- Tab-based 對話框:
  - 「Providers」tab: 新增/移除/啟用/停用 Provider
    - 每個 Provider: 類型下拉選單、API Key 輸入、標籤、測試連線按鈕
  - 「一般」tab: 輪詢間隔、主題選擇、開機啟動

### Phase 4: 背景輪詢 (Step 10)

**Step 10: 輪詢管理 (`poller.py`)** *depends on Steps 5, 6, 7*
- 使用 `QTimer` 定期觸發各 Provider 的 `fetch_usage()`
- 每個 Provider 獨立 `QThread` 避免 UI 阻塞
- Signal/Slot 機制: Worker 完成 → 更新 UI + 寫入 SQLite
- 錯誤處理: 網路失敗時顯示最後成功資料 + 錯誤訊息
- 支援手動觸發立即刷新

### Phase 5: 未來 Provider (Step 11, 非初版範圍)

**Step 11: OpenAI + GitHub Copilot** *不在初版範圍*
- OpenAI: `GET /v1/organization/usage/completions` + Admin Key
- GitHub Copilot: `GET /users/{username}/settings/billing/premium_request/usage` + PAT
- 架構已預留，只需實作對應的 Provider 子類別

---

## 關鍵檔案

- `app/providers/base.py` — BaseProvider ABC 和 UsageData/RateLimits dataclass
- `app/core/config_manager.py` — API Key 用 `keyring` 加密存 Windows Credential Manager
- `app/core/poller.py` — QThread + QTimer 背景輪詢
- `app/core/data_store.py` — SQLite 歷史資料
- `app/main_window.py` — 主視窗佈局
- `app/widgets/provider_card.py` — 核心顯示 Widget
- `app/providers/claude.py` — Anthropic Admin API 整合
- `app/providers/gemini.py` — Gemini 用量追蹤

---

## 驗證步驟

1. **單元測試**: 對各 Provider 的 API 回應解析寫測試 (mock HTTP response)
2. **連線測試**: 用 `test_connection()` 驗證 API Key 有效性
3. **UI 測試**: 啟動 app → 新增 Claude Provider → 輸入 Admin Key → 測試連線 → 確認卡片顯示用量
4. **輪詢測試**: 設定 60 秒輪詢 → 觀察 UI 自動更新 → 確認 SQLite 有寫入紀錄
5. **錯誤測試**: 斷網 → 確認 UI 顯示錯誤狀態但不崩潰 → 恢復後自動恢復
6. **設定測試**: 新增/移除 Provider → 重啟 app → 確認設定保留、API Key 安全存儲

---

## 決策與範圍

- **初版範圍**: Claude (Admin API) + Gemini (rate limit 資訊 + 手動追蹤)
- **排除範圍**: OpenAI、GitHub Copilot（架構預留但不實作）
- **API Key 安全**: 使用 `keyring` + Windows Credential Manager，不存明文
- **Gemini 限制**: 因無官方用量 API，初版先顯示 rate limit 表和手動輸入的統計
- **資料更新頻率**: 預設 5 分鐘（Claude API 數據延遲約 5 分鐘）

## Further Considerations

1. **Gemini 用量追蹤的取捨**: 因 Google AI Studio 無用量 API，可考慮 (A) 只顯示已知 rate limits 和定價資訊、(B) 未來做瀏覽器擴展抓取 dashboard 資料、(C) 若用戶有 GCP 專案走 Cloud Monitoring API。建議初版走 A。
2. **打包部署**: 可用 PyInstaller 打包成 .exe，但不在初版範圍內。需要時再加。
3. **Claude Code 專屬 usage**: Anthropic 有 `/v1/organizations/usage_report/claude_code` 端點追蹤 Claude Code 活動（session 數、程式碼行數等），可在 Claude Provider 中額外顯示此資訊。
