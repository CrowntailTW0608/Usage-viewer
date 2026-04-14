# GAI Usage Viewer

即時監控多家 GAI 服務用量的 Windows 桌面應用程式。

## 功能

- **多 Provider 支援** — 同時監控 Claude (Anthropic)、Gemini (Google AI Studio) 等服務
- **即時用量顯示** — Token 輸入/輸出/快取、費用 (USD)
- **速率限制** — RPM / TPM / RPD 視覺化進度條
- **歷史趨勢圖表** — 7 天 / 30 天用量折線圖
- **背景輪詢** — 可設定間隔自動刷新
- **安全金鑰管理** — API Key 透過 Windows Credential Manager 加密存儲
- **系統托盤** — 最小化到工作列

## 支援的 Provider

| Provider | 用量來源 | 需要的 Key |
|----------|----------|------------|
| Claude (Anthropic) | Admin API 或本地追蹤 | API Key (`sk-ant-api03-...`) 或 Admin Key (`sk-ant-admin-...`) |
| Gemini (Google AI Studio) | Tier Rate Limits 顯示 | Gemini API Key |

> **備註**: Claude 一般 API Key 可連線和顯示模型清單；Admin Key 才能查詢歷史用量（需組織帳號）。Gemini 目前無官方用量查詢 API，顯示各 Tier 的速率限制資訊。

## 快速開始

```bash
# 建立虛擬環境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 安裝依賴
pip install -r requirements.txt

# 啟動
python main.py
```

首次啟動後點選上方工具列「設定」→ 新增 Provider → 輸入 API Key → 測試連線。

## 專案結構

```
├── main.py                     # 應用入口
├── requirements.txt            # 依賴
├── app/
│   ├── main_window.py          # 主視窗 (PyQt6)
│   ├── settings_dialog.py      # Provider 管理對話框
│   ├── core/
│   │   ├── config_manager.py   # 設定管理 + keyring 金鑰存儲
│   │   ├── data_store.py       # SQLite 歷史用量儲存
│   │   └── poller.py           # QThreadPool 背景輪詢
│   ├── providers/
│   │   ├── base.py             # BaseProvider ABC + 資料模型
│   │   ├── claude.py           # Anthropic API 整合
│   │   └── gemini.py           # Google AI Studio 整合
│   └── widgets/
│       ├── provider_card.py    # Provider 顯示卡片
│       └── usage_chart.py      # 歷史趨勢圖表 (QChart)
```

## 依賴

- Python 3.8+
- PyQt6 + PyQt6-Charts
- requests
- keyring (Windows Credential Manager)

## 擴展 Provider

實作 `BaseProvider` 抽象類別即可新增 Provider：

```python
from app.providers.base import BaseProvider, UsageData, RateLimits

class MyProvider(BaseProvider):
    provider_type = "my_service"
    provider_display_name = "My Service"

    def fetch_usage(self, start, end) -> UsageData: ...
    def get_rate_limits(self) -> RateLimits | None: ...
    def test_connection(self) -> bool: ...
```

然後在 `app/core/poller.py` 和 `app/settings_dialog.py` 的 `PROVIDER_TYPES` 字典中註冊。

## 授權

MIT