from __future__ import annotations

from typing import Dict, List, Optional, Type

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.config_manager import ConfigManager
from app.providers.base import BaseProvider
from app.providers.claude import ClaudeProvider
from app.providers.gemini import GeminiProvider

# 可用 provider 類型 → class 映射
PROVIDER_TYPES: Dict[str, Type[BaseProvider]] = {
    "claude": ClaudeProvider,
    "gemini": GeminiProvider,
}


class SettingsDialog(QDialog):
    def __init__(self, config: ConfigManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("設定")
        self.setMinimumSize(560, 420)
        self._config = config
        self._changed = False

        self._build_ui()
        self._load_providers()

    # ── UI ──────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._build_providers_tab(), "Providers")
        tabs.addTab(self._build_general_tab(), "一般")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ── providers tab ───────────────────────────────────

    def _build_providers_tab(self) -> QWidget:
        tab = QWidget()
        layout = QHBoxLayout(tab)

        # 左側 list
        left = QVBoxLayout()
        self._provider_list = QListWidget()
        self._provider_list.currentRowChanged.connect(self._on_provider_selected)
        left.addWidget(self._provider_list)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("新增")
        add_btn.clicked.connect(self._on_add_provider)
        btn_row.addWidget(add_btn)
        self._remove_btn = QPushButton("移除")
        self._remove_btn.clicked.connect(self._on_remove_provider)
        self._remove_btn.setEnabled(False)
        btn_row.addWidget(self._remove_btn)
        left.addLayout(btn_row)
        layout.addLayout(left, 1)

        # 右側 detail form
        self._detail_group = QGroupBox("Provider 設定")
        self._detail_form = QFormLayout(self._detail_group)

        self._type_combo = QComboBox()
        self._type_combo.addItems(list(PROVIDER_TYPES.keys()))
        self._type_combo.currentTextChanged.connect(self._on_type_changed)
        self._detail_form.addRow("類型:", self._type_combo)

        self._label_edit = QLineEdit()
        self._detail_form.addRow("標籤:", self._label_edit)

        self._key_edit = QLineEdit()
        self._key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_edit.setPlaceholderText("輸入 API Key")
        self._detail_form.addRow("API Key:", self._key_edit)

        # Gemini tier 選擇 (只在 gemini 時顯示)
        self._tier_combo = QComboBox()
        self._tier_combo.addItems(GeminiProvider.available_tiers())
        self._tier_label = QLabel("Tier:")
        self._detail_form.addRow(self._tier_label, self._tier_combo)
        self._tier_label.hide()
        self._tier_combo.hide()

        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(60, 3600)
        self._interval_spin.setSingleStep(60)
        self._interval_spin.setValue(300)
        self._interval_spin.setSuffix(" 秒")
        self._detail_form.addRow("輪詢間隔:", self._interval_spin)

        self._test_btn = QPushButton("測試連線")
        self._test_btn.clicked.connect(self._on_test_connection)
        self._detail_form.addRow("", self._test_btn)

        self._detail_group.setEnabled(False)
        layout.addWidget(self._detail_group, 2)

        return tab

    # ── general tab ─────────────────────────────────────

    def _build_general_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)

        self._global_interval = QSpinBox()
        self._global_interval.setRange(60, 3600)
        self._global_interval.setSingleStep(60)
        self._global_interval.setSuffix(" 秒")
        ui = self._config.get_ui_settings()
        self._global_interval.setValue(ui.get("refresh_interval", 300))
        form.addRow("全域刷新間隔:", self._global_interval)

        return tab

    # ── load / save ─────────────────────────────────────

    def _load_providers(self) -> None:
        self._provider_list.clear()
        for p in self._config.get_providers():
            label = p.get("label", p.get("type", "unknown"))
            item = QListWidgetItem(f"[{p['type']}] {label}")
            self._provider_list.addItem(item)

    def _save_all(self) -> None:
        # 儲存目前正在編輯的 provider
        self._save_current_detail()

        # 儲存 UI 設定
        ui = self._config.get_ui_settings()
        ui["refresh_interval"] = self._global_interval.value()
        self._config.set("ui", ui)

    def _save_current_detail(self) -> None:
        row = self._provider_list.currentRow()
        if row < 0:
            return
        providers = self._config.get_providers()
        if row >= len(providers):
            return

        p = providers[row]
        p["type"] = self._type_combo.currentText()
        p["label"] = self._label_edit.text() or p["type"]
        p["poll_interval"] = self._interval_spin.value()
        if p["type"] == "gemini":
            p["tier"] = self._tier_combo.currentText()

        # 儲存 API Key
        key_id = f"{p['type']}:{p['label']}"
        key_text = self._key_edit.text().strip()
        if key_text:
            self._config.save_api_key(key_id, key_text)

        self._config.update_provider(row, p)

    # ── slots ───────────────────────────────────────────

    def _on_provider_selected(self, row: int) -> None:
        if row < 0:
            self._detail_group.setEnabled(False)
            self._remove_btn.setEnabled(False)
            return

        self._detail_group.setEnabled(True)
        self._remove_btn.setEnabled(True)

        providers = self._config.get_providers()
        if row >= len(providers):
            return
        p = providers[row]

        self._type_combo.setCurrentText(p.get("type", "claude"))
        self._label_edit.setText(p.get("label", ""))
        self._interval_spin.setValue(p.get("poll_interval", 300))

        # 載入 API Key
        key_id = f"{p['type']}:{p.get('label', '')}"
        stored_key = self._config.load_api_key(key_id)
        self._key_edit.setText(stored_key or "")

        # tier
        if p.get("type") == "gemini":
            self._tier_combo.setCurrentText(p.get("tier", "free"))

        self._on_type_changed(p.get("type", "claude"))

    def _on_type_changed(self, ptype: str) -> None:
        is_gemini = ptype == "gemini"
        self._tier_label.setVisible(is_gemini)
        self._tier_combo.setVisible(is_gemini)

    def _on_add_provider(self) -> None:
        ptype = "claude"
        label = f"新 Provider {self._provider_list.count() + 1}"
        self._config.add_provider({"type": ptype, "label": label})
        self._load_providers()
        self._provider_list.setCurrentRow(self._provider_list.count() - 1)
        self._changed = True

    def _on_remove_provider(self) -> None:
        row = self._provider_list.currentRow()
        if row < 0:
            return
        reply = QMessageBox.question(
            self,
            "確認移除",
            "確定要移除此 Provider 嗎？API Key 也會一併刪除。",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._config.remove_provider(row)
            self._load_providers()
            self._changed = True

    def _on_test_connection(self) -> None:
        ptype = self._type_combo.currentText()
        key = self._key_edit.text().strip()
        if not key:
            QMessageBox.warning(self, "錯誤", "請先輸入 API Key")
            return

        cls = PROVIDER_TYPES.get(ptype)
        if not cls:
            QMessageBox.warning(self, "錯誤", f"未知的 Provider 類型: {ptype}")
            return

        self._test_btn.setEnabled(False)
        self._test_btn.setText("測試中...")

        try:
            if ptype == "gemini":
                provider = cls(key, tier=self._tier_combo.currentText())
            else:
                provider = cls(key)

            ok = provider.test_connection()
            if ok:
                msg = "連線成功！"
                if ptype == "claude" and not provider.is_admin_key():
                    msg += (
                        "\n\n注意：你使用的是一般 API Key，"
                        "無法查詢用量資料。\n"
                        "如需查用量，請至 console.anthropic.com\n"
                        "→ Settings → Admin Keys 取得 Admin Key\n"
                        "（格式為 sk-ant-admin-...）"
                    )
                QMessageBox.information(self, "成功", msg)
            else:
                QMessageBox.warning(self, "失敗", "連線失敗，請檢查 API Key。")
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"連線錯誤:\n{e}")
        finally:
            self._test_btn.setEnabled(True)
            self._test_btn.setText("測試連線")

    def _on_ok(self) -> None:
        self._save_all()
        self._changed = True
        self.accept()

    @property
    def changed(self) -> bool:
        return self._changed
