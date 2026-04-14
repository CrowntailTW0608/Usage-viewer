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

        # token 用量區
        token_grid = QGridLayout()
        token_grid.setSpacing(6)

        token_grid.addWidget(self._make_label("輸入 Tokens:"), 0, 0)
        self._input_val = QLabel("—")
        self._input_val.setStyleSheet("color: #4A9EFF; font-weight: bold;")
        token_grid.addWidget(self._input_val, 0, 1)

        token_grid.addWidget(self._make_label("輸出 Tokens:"), 1, 0)
        self._output_val = QLabel("—")
        self._output_val.setStyleSheet("color: #FF6B6B; font-weight: bold;")
        token_grid.addWidget(self._output_val, 1, 1)

        token_grid.addWidget(self._make_label("快取 Tokens:"), 2, 0)
        self._cached_val = QLabel("—")
        self._cached_val.setStyleSheet("color: #66BB6A; font-weight: bold;")
        token_grid.addWidget(self._cached_val, 2, 1)

        token_grid.addWidget(self._make_label("費用 (USD):"), 3, 0)
        self._cost_val = QLabel("—")
        self._cost_val.setStyleSheet("color: #FFA726; font-weight: bold;")
        token_grid.addWidget(self._cost_val, 3, 1)

        detail_layout.addLayout(token_grid)

        # rate limits 區
        self._rate_limits_section = QWidget()
        rl_layout = QVBoxLayout(self._rate_limits_section)
        rl_layout.setContentsMargins(0, 8, 0, 0)
        rl_label = QLabel("速率限制")
        rl_label.setStyleSheet("color: #aaa; font-size: 12px;")
        rl_layout.addWidget(rl_label)

        rl_grid = QGridLayout()
        rl_grid.setSpacing(4)

        rl_grid.addWidget(self._make_label("RPM:"), 0, 0)
        self._rpm_bar = QProgressBar()
        self._rpm_bar.setTextVisible(True)
        self._rpm_bar.setFixedHeight(18)
        rl_grid.addWidget(self._rpm_bar, 0, 1)

        rl_grid.addWidget(self._make_label("TPM:"), 1, 0)
        self._tpm_bar = QProgressBar()
        self._tpm_bar.setTextVisible(True)
        self._tpm_bar.setFixedHeight(18)
        rl_grid.addWidget(self._tpm_bar, 1, 1)

        rl_grid.addWidget(self._make_label("RPD:"), 2, 0)
        self._rpd_bar = QProgressBar()
        self._rpd_bar.setTextVisible(True)
        self._rpd_bar.setFixedHeight(18)
        rl_grid.addWidget(self._rpd_bar, 2, 1)

        rl_layout.addLayout(rl_grid)
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
