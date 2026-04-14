from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Type

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, QTimer, pyqtSignal, pyqtSlot

from app.core.config_manager import ConfigManager
from app.core.data_store import DataStore
from app.providers.base import BaseProvider, ProviderStatus, UsageData
from app.providers.claude import ClaudeProvider
from app.providers.gemini import GeminiProvider

logger = logging.getLogger(__name__)

PROVIDER_CLASSES: Dict[str, Type[BaseProvider]] = {
    "claude": ClaudeProvider,
    "gemini": GeminiProvider,
}

# 時間範圍選項對應的天數
RANGE_DAYS = {0: 1, 1: 7, 2: 30}  # index → days


class WorkerSignals(QObject):
    finished = pyqtSignal(str, object)  # (provider_key, ProviderStatus)


class FetchRunnable(QRunnable):
    """在 QThreadPool 中執行的用量取得任務。"""

    def __init__(self, provider_key: str, provider: BaseProvider, days: int = 1):
        super().__init__()
        self.signals = WorkerSignals()
        self._key = provider_key
        self._provider = provider
        self._days = days
        self.setAutoDelete(True)

    @pyqtSlot()
    def run(self) -> None:
        status = ProviderStatus()
        try:
            now = datetime.utcnow()
            start = now - timedelta(days=self._days)

            usage = self._provider.fetch_usage(start, now)
            rate_limits = self._provider.get_rate_limits()

            status.connected = True
            status.last_updated = now
            status.usage = usage
            status.rate_limits = rate_limits
        except Exception as e:
            logger.error("Fetch failed for %s: %s", self._key, e)
            status.connected = False
            status.error_message = str(e)

        self.signals.finished.emit(self._key, status)


class Poller(QObject):
    """管理所有 Provider 的定期輪詢。"""

    provider_updated = pyqtSignal(str, object)  # (provider_key, ProviderStatus)
    all_updated = pyqtSignal()

    def __init__(self, config: ConfigManager, data_store: DataStore):
        super().__init__()
        self._config = config
        self._data_store = data_store
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.poll_all)
        self._pool = QThreadPool.globalInstance()
        self._range_days = 1
        self._pending = 0

    def start(self, interval_ms: Optional[int] = None) -> None:
        if interval_ms is None:
            ui = self._config.get_ui_settings()
            interval_ms = ui.get("refresh_interval", 300) * 1000
        self._timer.start(interval_ms)
        # 立即執行一次
        self.poll_all()

    def stop(self) -> None:
        self._timer.stop()

    def set_range(self, index: int) -> None:
        self._range_days = RANGE_DAYS.get(index, 1)

    def poll_all(self) -> None:
        providers = self._config.get_providers()
        enabled = [p for p in providers if p.get("enabled", True)]

        if not enabled:
            self.all_updated.emit()
            return

        self._pending = len(enabled)

        for p_cfg in enabled:
            ptype = p_cfg["type"]
            label = p_cfg.get("label", ptype)
            key_id = f"{ptype}:{label}"

            api_key = self._config.load_api_key(key_id)
            if not api_key:
                status = ProviderStatus(
                    connected=False,
                    error_message="未設定 API Key",
                )
                self.provider_updated.emit(key_id, status)
                self._pending -= 1
                if self._pending <= 0:
                    self.all_updated.emit()
                continue

            cls = PROVIDER_CLASSES.get(ptype)
            if not cls:
                self._pending -= 1
                if self._pending <= 0:
                    self.all_updated.emit()
                continue

            if ptype == "gemini":
                provider = cls(api_key, label, tier=p_cfg.get("tier", "free"))
            else:
                provider = cls(api_key, label)

            runnable = FetchRunnable(key_id, provider, self._range_days)
            runnable.signals.finished.connect(self._on_worker_done)
            self._pool.start(runnable)

    def _on_worker_done(self, provider_key: str, status: ProviderStatus) -> None:
        # 寫入歷史
        if status.usage and status.connected:
            self._data_store.save_usage(
                provider_key,
                status.usage,
            )

        self.provider_updated.emit(provider_key, status)

        self._pending -= 1
        if self._pending <= 0:
            self.all_updated.emit()
