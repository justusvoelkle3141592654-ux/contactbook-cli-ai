"""System monitor window: metric cards with live charts, disks and processes."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from desktop_organizer.app import dialogs, worker
from desktop_organizer.app.components import DATA_ROLE, BarDelegate, Table, item
from desktop_organizer.app.context import AppContext
from desktop_organizer.app.theming import ThemeManager
from desktop_organizer.app.tool_window import ToolWindow
from desktop_organizer.core.formatting import format_bytes, format_percent
from desktop_organizer.core.i18n import tr
from desktop_organizer.tools.system_monitor import SETTINGS
from desktop_organizer.tools.system_monitor.logic import (
    ProcessSnapshot,
    Reading,
    Sampler,
    disks,
    end_process,
    top_processes,
)

TOOL = "system_monitor"


def t(key: str, **kwargs: object) -> str:
    return tr(f"tool.{TOOL}.{key}", **kwargs)


class LineChart(QWidget):
    """Area chart of recent values. ``maximum=None`` scales to the largest value."""

    def __init__(self, theme: ThemeManager, maximum: float | None = 100.0) -> None:
        super().__init__()
        self._theme = theme
        self._maximum = maximum
        self._series: list[Sequence[float]] = []
        self.setMinimumHeight(72)

    def set_series(self, *series: Sequence[float]) -> None:
        self._series = list(series)
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        t_ = self._theme.tokens
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0, 4, 0, -2)
        grid = QPen(QColor(t_.divider))
        grid.setWidthF(1)
        p.setPen(grid)
        for fraction in (0.25, 0.5, 0.75):
            y = rect.top() + rect.height() * fraction
            p.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        top = self._maximum or max([1.0, *(max(s) if s else 0 for s in self._series)])
        colors = [t_.accent, t_.success]
        for index, values in enumerate(self._series):
            if len(values) < 2:
                continue
            step = rect.width() / (60 - 1)
            start_x = rect.right() - step * (len(values) - 1)
            points = [
                QPointF(start_x + i * step, rect.bottom() - rect.height() * min(v / top, 1.0))
                for i, v in enumerate(values)
            ]
            line = QPainterPath(points[0])
            for point in points[1:]:
                line.lineTo(point)
            color = QColor(colors[index % 2])
            if index == 0:
                area = QPainterPath(line)
                area.lineTo(points[-1].x(), rect.bottom())
                area.lineTo(points[0].x(), rect.bottom())
                area.closeSubpath()
                fill = QColor(color)
                fill.setAlpha(40)
                p.fillPath(area, fill)
            pen = QPen(color)
            pen.setWidthF(1.6)
            p.setPen(pen)
            p.drawPath(line)
        p.end()


class CoreBars(QWidget):
    """One thin vertical bar per CPU core."""

    def __init__(self, theme: ThemeManager) -> None:
        super().__init__()
        self._theme = theme
        self._values: list[float] = []
        self.setMinimumHeight(48)
        self.setMaximumHeight(64)

    def set_values(self, values: list[float]) -> None:
        self._values = values
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        if not self._values:
            return
        t_ = self._theme.tokens
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        count = len(self._values)
        gap = 4
        width = max(3.0, (self.width() - gap * (count - 1)) / count)
        for index, value in enumerate(self._values):
            x = index * (width + gap)
            p.setBrush(QColor(t_.nav_selected))
            p.drawRoundedRect(QRectF(x, 0, width, self.height()), 2, 2)
            height = self.height() * min(value, 100) / 100
            p.setBrush(QColor(t_.accent))
            p.drawRoundedRect(QRectF(x, self.height() - height, width, height), 2, 2)
        p.end()


class MetricCard(QFrame):
    def __init__(self, theme: ThemeManager, chart: QWidget | None = None) -> None:
        super().__init__()
        self.setObjectName("Panel")
        self.title = QLabel()
        self.title.setProperty("textStyle", "secondary")
        self.value = QLabel("–")
        self.value.setProperty("textStyle", "display")
        self.detail = QLabel()
        self.detail.setProperty("textStyle", "caption")
        self.detail.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addWidget(self.detail)
        if chart is not None:
            layout.addSpacing(6)
            layout.addWidget(chart, 1)


class SystemMonitorWindow(ToolWindow):
    tool_id = TOOL
    icon = "activity"
    settings_fields = SETTINGS

    def __init__(self, context: AppContext) -> None:
        super().__init__(context)
        self.sampler = Sampler()
        self._process_task: worker.Worker | None = None

        self.cpu_chart = LineChart(context.theme)
        self.memory_chart = LineChart(context.theme)
        self.net_chart = LineChart(context.theme, None)
        self.cores = CoreBars(context.theme)
        self.cpu_card = MetricCard(context.theme, self.cpu_chart)
        self.memory_card = MetricCard(context.theme, self.memory_chart)
        self.net_card = MetricCard(context.theme, self.net_chart)
        self.cores_card = MetricCard(context.theme, self.cores)
        self.battery_card = MetricCard(context.theme)
        grid = QGridLayout()
        grid.setSpacing(12)
        grid.addWidget(self.cpu_card, 0, 0)
        grid.addWidget(self.memory_card, 0, 1)
        grid.addWidget(self.net_card, 0, 2)
        grid.addWidget(self.cores_card, 1, 0, 1, 2)
        grid.addWidget(self.battery_card, 1, 2)
        self.content.addLayout(grid)

        self.tabs = QTabWidget()
        self.disk_table = Table(5)
        self.disk_table.setItemDelegateForColumn(1, BarDelegate(context.theme, self))
        for column, width in ((1, 260), (2, 120), (3, 120), (4, 100)):
            self.disk_table.setColumnWidth(column, width)
        processes_page = QWidget()
        processes_layout = QVBoxLayout(processes_page)
        processes_layout.setContentsMargins(0, 8, 0, 0)
        head = QHBoxLayout()
        self.process_label = QLabel()
        self.process_label.setProperty("textStyle", "caption")
        self.end_button = QPushButton()
        self.end_button.clicked.connect(self.end_selected)
        head.addWidget(self.process_label, 1)
        head.addWidget(self.end_button)
        processes_layout.addLayout(head)
        self.process_table = Table(5)
        for column, width in ((1, 90), (2, 100), (3, 120), (4, 200)):
            self.process_table.setColumnWidth(column, width)
        self.process_table.context_requested.connect(self._process_menu)
        self.process_table.sortByColumn(
            2 if self.option("process_sort") == "cpu" else 3, Qt.SortOrder.DescendingOrder
        )
        processes_layout.addWidget(self.process_table, 1)
        self.tabs.addTab(processes_page, "")
        self.tabs.addTab(self.disk_table, "")
        self.content.addWidget(self.tabs, 1)

        self.uptime = QLabel()
        self.uptime.setProperty("textStyle", "caption")
        self.footer.addWidget(self.uptime, 1)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.tick)
        self._disk_timer = QTimer(self)
        self._disk_timer.timeout.connect(self.refresh_disks)
        self._disk_timer.start(15_000)
        self.retranslate()
        self._apply_interval()
        QTimer.singleShot(300, self.tick)
        self.refresh_disks()

    def retranslate(self) -> None:
        self.cpu_card.title.setText(t("cpu"))
        self.memory_card.title.setText(t("memory"))
        self.net_card.title.setText(t("network"))
        self.cores_card.title.setText(t("cores"))
        self.battery_card.title.setText(t("battery"))
        self.tabs.setTabText(0, t("tab.processes"))
        self.tabs.setTabText(1, t("tab.disks"))
        self.end_button.setText(t("end"))
        self.disk_table.set_headers(
            [t("col.drive"), t("col.usage"), t("col.free"), t("col.total"), t("col.fs")]
        )
        self.process_table.set_headers(
            [t("col.process"), t("col.pid"), t("col.cpu"), t("col.ram"), t("col.user")]
        )

    def _apply_interval(self) -> None:
        self._timer.start(self.option("refresh_seconds") * 1000)
        self.cores_card.setVisible(self.option("show_cores"))

    def settings_changed(self) -> None:
        self._apply_interval()

    def tick(self) -> None:
        if not self.isVisible():
            return  # no polling while minimized or hidden
        lang = self.context.translator.language
        reading: Reading = self.sampler.sample()
        self.cpu_card.value.setText(format_percent(reading.cpu, lang))
        self.cpu_card.detail.setText(t("cpu.detail", cores=len(reading.per_core)))
        self.cpu_chart.set_series(list(self.sampler.cpu_history))
        self.memory_card.value.setText(
            format_percent(100 * reading.memory_used / max(reading.memory_total, 1), lang)
        )
        self.memory_card.detail.setText(
            t(
                "memory.detail",
                used=format_bytes(reading.memory_used, lang),
                total=format_bytes(reading.memory_total, lang),
                swap=format_bytes(reading.swap_used, lang),
            )
        )
        self.memory_chart.set_series(list(self.sampler.memory_history))
        self.net_card.value.setText(f"{format_bytes(int(reading.net_down), lang)}/s")
        self.net_card.detail.setText(
            t("network.detail", up=f"{format_bytes(int(reading.net_up), lang)}/s")
        )
        self.net_chart.set_series(list(self.sampler.down_history), list(self.sampler.up_history))
        self.cores.set_values(reading.per_core)
        self.cores_card.value.setText(format_percent(max(reading.per_core or [0]), lang))
        self.cores_card.detail.setText(t("cores.detail"))
        if reading.battery_percent is None:
            self.battery_card.value.setText("–")
            self.battery_card.detail.setText(t("battery.none"))
        else:
            self.battery_card.value.setText(format_percent(reading.battery_percent, lang))
            if reading.battery_plugged:
                self.battery_card.detail.setText(t("battery.plugged"))
            elif reading.battery_seconds_left:
                minutes = reading.battery_seconds_left // 60
                self.battery_card.detail.setText(
                    t("battery.left", hours=minutes // 60, minutes=minutes % 60)
                )
            else:
                self.battery_card.detail.setText(t("battery.discharging"))
        hours = int(reading.uptime // 3600)
        self.uptime.setText(t("uptime", days=hours // 24, hours=hours % 24))
        self._refresh_processes()

    def _refresh_processes(self) -> None:
        if self._process_task is not None or self.tabs.currentIndex() != 0:
            return
        limit, sort = self.option("process_count"), self.option("process_sort")
        task = worker.Worker(lambda _job: top_processes(limit, sort))
        self._process_task = task
        task.signals.finished.connect(self._processes_ready)
        task.signals.failed.connect(lambda _m: setattr(self, "_process_task", None))
        worker.start(task)

    def _processes_ready(self, snapshot: Any) -> None:
        self._process_task = None
        assert isinstance(snapshot, ProcessSnapshot)
        lang = self.context.translator.language
        selected = {
            self.process_table.source.item(r, 1).text() for r in self.process_table.selected_rows()
        }
        table = self.process_table
        table.setSortingEnabled(False)
        table.clear_rows()
        for proc in snapshot.processes:
            table.source.appendRow(
                [
                    item(proc.name, data=proc.pid),
                    item(str(proc.pid), sort=proc.pid),
                    item(format_percent(proc.cpu, lang), sort=proc.cpu),
                    item(format_bytes(proc.memory, lang), sort=proc.memory),
                    item(proc.user.split("\\")[-1]),
                ]
            )
        table.setSortingEnabled(True)
        for row in range(table.source.rowCount()):
            if table.source.item(row, 1).text() in selected:
                table.selectRow(table.proxy.mapFromSource(table.source.index(row, 0)).row())
        self.process_label.setText(
            t("processes", shown=len(snapshot.processes), total=snapshot.total)
        )

    def refresh_disks(self) -> None:
        lang = self.context.translator.language
        table = self.disk_table
        table.setSortingEnabled(False)
        table.clear_rows()
        for disk in disks():
            usage = item(format_percent(disk.fraction * 100, lang), sort=disk.fraction)
            usage.setData(disk.fraction, DATA_ROLE)
            usage.setText("")
            table.source.appendRow(
                [
                    item(disk.mount),
                    usage,
                    item(format_bytes(disk.free, lang), sort=disk.free),
                    item(format_bytes(disk.total, lang), sort=disk.total),
                    item(disk.filesystem),
                ]
            )
        table.setSortingEnabled(True)

    def _process_menu(self, row: int, pos: Any) -> None:
        menu = QMenu(self)
        menu.addAction(t("end"), lambda: self._end(row))
        menu.exec(pos)

    def end_selected(self) -> None:
        rows = self.process_table.selected_rows()
        if rows:
            self._end(rows[0])

    def _end(self, row: int) -> None:
        pid = int(self.process_table.source.item(row, 0).data(DATA_ROLE))
        name = self.process_table.source.item(row, 0).text()
        if not dialogs.confirm_destructive(
            self, t("end.title", name=name), t("end.body"), t("end"), tr("common.cancel")
        ):
            return
        error = end_process(pid)
        if error is None:
            self.info.show_message("success", t("end.done", name=name))
        else:
            message = t("end.gone", name=name) if error == "gone" else t("end.denied", name=name)
            self.info.show_message("warning", message)

    def theme_changed(self) -> None:
        for widget in (self.cpu_chart, self.memory_chart, self.net_chart, self.cores):
            widget.update()

    def screenshot_prepare(self) -> None:
        """Collect some real samples so the charts are not empty (screenshots only)."""
        import time as _time

        for _ in range(25):
            self.sampler.sample()
            _time.sleep(0.04)
        self.tick()
        self._processes_ready(
            top_processes(self.option("process_count"), self.option("process_sort"))
        )
