from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QScrollArea,
    QStatusBar,
    QSystemTrayIcon,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QMenu,
    QApplication,
)

from app.core.config_manager import ConfigManager
from app.core.data_store import DataStore
from app.core.poller import Poller
from app.providers.base import BaseProvider, ProviderStatus


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GAI Usage Viewer")
        self.setMinimumSize(900, 620)

        self._config = ConfigManager()
        self._data_store = DataStore()
        self._provider_cards: List[QWidget] = []
        self._card_map: Dict[str, QWidget] = {}  # provider_key → card

        self._build_toolbar()
        self._build_central()
        self._build_statusbar()
        self._build_tray()

        # 輪詢器
        self._poller = Poller(self._config, self._data_store)
        self._poller.provider_updated.connect(self._on_provider_updated)
        self._poller.all_updated.connect(self._on_all_updated)

        # 啟動時載入 providers
        self._reload_providers()
        self._poller.start()

    # ── toolbar ─────────────────────────────────────────

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("主工具列")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self._refresh_action = QAction("刷新", self)
        self._refresh_action.setToolTip("立即刷新所有 Provider 用量")
        self._refresh_action.triggered.connect(self._on_refresh)
        toolbar.addAction(self._refresh_action)

        toolbar.addSeparator()

        # 時間範圍選擇
        range_label = QLabel("  時間範圍: ")
        toolbar.addWidget(range_label)
        self._range_combo = QComboBox()
        self._range_combo.addItems(["今天", "7 天", "30 天"])
        self._range_combo.currentIndexChanged.connect(self._on_range_changed)
        toolbar.addWidget(self._range_combo)

        toolbar.addSeparator()

        self._settings_action = QAction("設定", self)
        self._settings_action.setToolTip("管理 Provider 和應用程式設定")
        self._settings_action.triggered.connect(self._on_settings)
        toolbar.addAction(self._settings_action)

    # ── central scroll area ─────────────────────────────

    def _build_central(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._cards_layout.setSpacing(12)
        self._cards_layout.setContentsMargins(16, 16, 16, 16)

        # 佔位訊息
        self._placeholder = QLabel("尚未設定任何 Provider。\n請點選上方「設定」新增。")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: #888; font-size: 14px;")
        self._cards_layout.addWidget(self._placeholder)

        scroll.setWidget(self._cards_container)
        self.setCentralWidget(scroll)

    # ── status bar ──────────────────────────────────────

    def _build_statusbar(self) -> None:
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("就緒")
        self._status_bar.addPermanentWidget(self._status_label)

    def update_status(self, text: str) -> None:
        self._status_label.setText(text)

    # ── system tray ─────────────────────────────────────

    def _build_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self._tray = QSystemTrayIcon(self)
        self._tray.setToolTip("GAI Usage Viewer")

        tray_menu = QMenu()
        show_action = tray_menu.addAction("顯示")
        show_action.triggered.connect(self._show_from_tray)
        quit_action = tray_menu.addAction("結束")
        quit_action.triggered.connect(self._quit_app)
        self._tray.setContextMenu(tray_menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.activateWindow()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_from_tray()

    def _quit_app(self) -> None:
        """完整清理後結束應用程式。"""
        self._poller.stop()
        self._data_store.close()
        if hasattr(self, "_tray"):
            self._tray.hide()
        QApplication.quit()

    def closeEvent(self, event) -> None:
        self._quit_app()
        event.accept()

    # ── card management ─────────────────────────────────

    def add_provider_card(self, card: QWidget) -> None:
        self._placeholder.hide()
        self._cards_layout.addWidget(card)
        self._provider_cards.append(card)

    def clear_cards(self) -> None:
        for card in self._provider_cards:
            self._cards_layout.removeWidget(card)
            card.deleteLater()
        self._provider_cards.clear()

    def refresh_cards(self) -> None:
        if not self._provider_cards:
            self._placeholder.show()
        else:
            self._placeholder.hide()

    def _reload_providers(self) -> None:
        """根據 config 重建所有 provider 卡片。"""
        from app.widgets.provider_card import ProviderCard

        self.clear_cards()
        self._card_map.clear()
        providers = self._config.get_providers()
        for p in providers:
            if not p.get("enabled", True):
                continue
            label = p.get("label", p["type"])
            key_id = f"{p['type']}:{label}"
            card = ProviderCard(
                provider_type=p["type"],
                display_name=label,
            )
            # 若有 rate limits (如 Gemini)，立即顯示
            if p["type"] == "gemini":
                from app.providers.gemini import GeminiProvider
                gp = GeminiProvider("", tier=p.get("tier", "free"))
                rl = gp.get_rate_limits()
                if rl:
                    card.update_rate_limits(rl)
            self.add_provider_card(card)
            self._card_map[key_id] = card
        self.refresh_cards()
        self.update_status(f"已載入 {len(self._provider_cards)} 個 Provider")

    # ── slots ───────────────────────────────────────────

    def _on_refresh(self) -> None:
        self.update_status("正在刷新...")
        self._poller.poll_all()

    def _on_range_changed(self, index: int) -> None:
        self._poller.set_range(index)
        self._poller.poll_all()

    def _on_provider_updated(self, key: str, status: ProviderStatus) -> None:
        card = self._card_map.get(key)
        if card:
            card.update_status(status)

            # 更新歷史圖表
            history = self._data_store.get_daily_summary(key, days=7)
            if history:
                days = [h["day"] for h in reversed(history)]
                inp = [h["total_input"] for h in reversed(history)]
                out = [h["total_output"] for h in reversed(history)]
                card.update_chart(days, inp, out)

    def _on_all_updated(self) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        self.update_status(f"最後更新: {now}")

    def _on_settings(self) -> None:
        from app.settings_dialog import SettingsDialog

        self._poller.stop()
        dlg = SettingsDialog(self._config, self)
        dlg.exec()
        if dlg.changed:
            self._reload_providers()
        self._poller.start()
