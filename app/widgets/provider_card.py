from __future__ import annotations

from typing import Dict, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.providers.base import ProviderStatus, RateLimits, UsageData
from app.widgets.usage_chart import UsageChart


class ProviderCard(QFrame):
    """單一 Provider 的顯示卡片。"""

    def __init__(
        self,
        provider_type: str,
        display_name: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._provider_type = provider_type
        self._display_name = display_name
        self._expanded = True

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            ProviderCard {
                background: #2b2b2b;
                border: 1px solid #444;
                border-radius: 8px;
            }
        """)

        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)

        # ── header row ──────────────────────────────────
        header = QHBoxLayout()

        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("color: #888; font-size: 16px;")
        self._status_dot.setFixedWidth(24)
        header.addWidget(self._status_dot)

        self._title = QLabel(self._display_name)
        self._title.setStyleSheet("font-size: 15px; font-weight: bold; color: #eee;")
        header.addWidget(self._title)

        header.addStretch()

        self._toggle_btn = QPushButton("▼")
        self._toggle_btn.setFixedSize(28, 28)
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setStyleSheet("color: #aaa;")
        self._toggle_btn.clicked.connect(self._toggle_expand)
        header.addWidget(self._toggle_btn)

        main_layout.addLayout(header)

        # ── detail container (可展開/收合) ──────────────
        self._detail = QWidget()
        detail_layout = QVBoxLayout(self._detail)
        detail_layout.setContentsMargins(28, 0, 0, 0)
        detail_layout.setSpacing(6)

        # token 用量區 — 橫列排列
        token_row = QHBoxLayout()
        token_row.setSpacing(16)

        token_row.addLayout(self._make_metric("輸入", "#4A9EFF"))
        self._input_val = token_row.itemAt(token_row.count() - 1).layout().itemAt(1).widget()

        token_row.addLayout(self._make_metric("輸出", "#FF6B6B"))
        self._output_val = token_row.itemAt(token_row.count() - 1).layout().itemAt(1).widget()

        token_row.addLayout(self._make_metric("快取", "#66BB6A"))
        self._cached_val = token_row.itemAt(token_row.count() - 1).layout().itemAt(1).widget()

        token_row.addLayout(self._make_metric("費用", "#FFA726"))
        self._cost_val = token_row.itemAt(token_row.count() - 1).layout().itemAt(1).widget()

        token_row.addStretch()
        detail_layout.addLayout(token_row)

        # rate limits 區 — 橫列排列
        self._rate_limits_section = QWidget()
        rl_layout = QHBoxLayout(self._rate_limits_section)
        rl_layout.setContentsMargins(0, 4, 0, 0)
        rl_layout.setSpacing(12)

        rl_title = QLabel("速率限制")
        rl_title.setStyleSheet("color: #aaa; font-size: 12px;")
        rl_title.setFixedWidth(60)
        rl_layout.addWidget(rl_title)

        for name in ("RPM", "TPM", "RPD"):
            lbl = QLabel(f"{name}:")
            lbl.setStyleSheet("color: #aaa; font-size: 12px;")
            lbl.setFixedWidth(35)
            rl_layout.addWidget(lbl)
            bar = QProgressBar()
            bar.setTextVisible(True)
            bar.setFixedHeight(16)
            bar.setMinimumWidth(100)
            rl_layout.addWidget(bar)
            setattr(self, f"_{name.lower()}_bar", bar)

        rl_layout.addStretch()
        self._rate_limits_section.hide()
        detail_layout.addWidget(self._rate_limits_section)

        # 歷史趨勢圖表
        self._chart = UsageChart()
        detail_layout.addWidget(self._chart)

        # 錯誤訊息
        self._error_label = QLabel()
        self._error_label.setStyleSheet("color: #FF5252; font-size: 12px;")
        self._error_label.hide()
        detail_layout.addWidget(self._error_label)

        main_layout.addWidget(self._detail)

    # ── update methods ──────────────────────────────────

    def update_status(self, status: ProviderStatus) -> None:
        if status.connected:
            self._status_dot.setStyleSheet("color: #66BB6A; font-size: 16px;")
        else:
            self._status_dot.setStyleSheet("color: #FF5252; font-size: 16px;")

        if status.usage:
            self.update_usage(status.usage)
        if status.rate_limits:
            self.update_rate_limits(status.rate_limits)
        if status.error_message:
            self._error_label.setText(status.error_message)
            self._error_label.show()
        else:
            self._error_label.hide()

    def update_usage(self, usage: UsageData) -> None:
        self._input_val.setText(self._format_number(usage.input_tokens))
        self._output_val.setText(self._format_number(usage.output_tokens))
        self._cached_val.setText(self._format_number(usage.cached_tokens))
        self._cost_val.setText(f"${usage.cost_usd:.4f}" if usage.cost_usd else "—")

    def update_rate_limits(self, rl: RateLimits) -> None:
        self._rate_limits_section.show()
        self._update_rl_bar(self._rpm_bar, rl.rpm_remaining, rl.rpm)
        self._update_rl_bar(self._tpm_bar, rl.tpm_remaining, rl.tpm)
        self._update_rl_bar(self._rpd_bar, rl.rpd_remaining, rl.rpd)

    def update_chart(self, days: list, input_vals: list, output_vals: list) -> None:
        self._chart.update_data(days, input_vals, output_vals)

    # ── helpers ─────────────────────────────────────────

    def _toggle_expand(self) -> None:
        self._expanded = not self._expanded
        self._detail.setVisible(self._expanded)
        self._toggle_btn.setText("▼" if self._expanded else "►")

    @staticmethod
    def _make_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #aaa; font-size: 13px;")
        lbl.setFixedWidth(110)
        return lbl

    @staticmethod
    def _make_metric(label_text: str, color: str) -> QVBoxLayout:
        """建立一組 label + value 的垂直佈局（用於橫列排列）。"""
        col = QVBoxLayout()
        col.setSpacing(2)
        lbl = QLabel(label_text)
        lbl.setStyleSheet("color: #aaa; font-size: 11px;")
        col.addWidget(lbl)
        val = QLabel("—")
        val.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 14px;")
        col.addWidget(val)
        return col

    @staticmethod
    def _format_number(n: int) -> str:
        if n >= 1_000_000:
            return f"{n / 1_000_000:.2f}M"
        if n >= 1_000:
            return f"{n / 1_000:.1f}K"
        return str(n)

    @staticmethod
    def _update_rl_bar(
        bar: QProgressBar,
        remaining: Optional[int],
        maximum: Optional[int],
    ) -> None:
        if maximum is None or maximum == 0:
            bar.setFormat("N/A")
            bar.setValue(0)
            bar.setMaximum(1)
            return
        bar.setMaximum(maximum)
        if remaining is not None:
            used = maximum - remaining
            bar.setValue(used)
            bar.setFormat(f"{used:,} / {maximum:,}")
        else:
            bar.setValue(0)
            bar.setFormat(f"上限 {maximum:,}")
