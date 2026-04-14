from __future__ import annotations

from typing import List, Optional, Tuple

from PyQt6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QWidget, QVBoxLayout


class UsageChart(QWidget):
    """嵌入式歷史趨勢圖表。"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._chart = QChart()
        self._chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self._chart.legend().setVisible(True)
        self._chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        self._chart.setMargins(QtCore_QMargins(4, 4, 4, 4))

        self._chart_view = QChartView(self._chart)
        self._chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._chart_view.setMinimumHeight(180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._chart_view)

    def update_data(
        self,
        days: List[str],
        input_values: List[int],
        output_values: List[int],
    ) -> None:
        self._chart.removeAllSeries()
        for axis in self._chart.axes():
            self._chart.removeAxis(axis)

        if not days:
            return

        input_series = QLineSeries()
        input_series.setName("輸入 Tokens")
        input_series.setColor(QColor("#4A9EFF"))

        output_series = QLineSeries()
        output_series.setName("輸出 Tokens")
        output_series.setColor(QColor("#FF6B6B"))

        max_val = 0
        for i, (inp, out) in enumerate(zip(input_values, output_values)):
            input_series.append(i, inp)
            output_series.append(i, out)
            max_val = max(max_val, inp, out)

        self._chart.addSeries(input_series)
        self._chart.addSeries(output_series)

        axis_x = QValueAxis()
        axis_x.setRange(0, max(len(days) - 1, 1))
        axis_x.setTickCount(min(len(days), 7))
        axis_x.setLabelFormat("%d")
        axis_x.setTitleText("天")
        self._chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        input_series.attachAxis(axis_x)
        output_series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setRange(0, max(max_val * 1.1, 1))
        axis_y.setTitleText("Tokens")
        self._chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        input_series.attachAxis(axis_y)
        output_series.attachAxis(axis_y)


def QtCore_QMargins(left: int, top: int, right: int, bottom: int):
    from PyQt6.QtCore import QMargins
    return QMargins(left, top, right, bottom)
