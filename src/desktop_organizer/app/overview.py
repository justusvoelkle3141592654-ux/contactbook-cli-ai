"""Main window: sidebar navigation, tools page, settings page and status line."""

from __future__ import annotations

import logging

from PySide6.QtCore import QByteArray, QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QKeyEvent, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from desktop_organizer import __version__
from desktop_organizer.app import dialogs
from desktop_organizer.app.context import AppContext
from desktop_organizer.app.settings_page import SettingsPage
from desktop_organizer.app.widgets import Meter, NavButton, SearchField, ToolCard
from desktop_organizer.core import system_info
from desktop_organizer.core.formatting import (
    format_bytes,
    format_datetime,
    format_duration,
    format_percent,
)
from desktop_organizer.core.i18n import tr
from desktop_organizer.core.paths import resources_dir
from desktop_organizer.tools.registry import CATEGORY_ORDER, Category, ToolSpec

log = logging.getLogger(__name__)

STATUS_INTERVAL_MS = 2000
TWO_COLUMN_MIN_WIDTH = 720
ALL = "all"


def matches(spec: ToolSpec, query: str) -> bool:
    if not query:
        return True
    needle = query.casefold()
    return needle in tr(spec.title_key).casefold() or needle in tr(spec.description_key).casefold()


def page_layout(widget: QWidget) -> QVBoxLayout:
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(32, 28, 32, 24)
    layout.setSpacing(4)
    return layout


class StatCell(QPushButton):
    """Small clickable summary: caption on top, value below."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("StatCell")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.caption = QLabel()
        self.caption.setProperty("textStyle", "caption")
        self.value = QLabel()
        self.value.setProperty("textStyle", "cardTitle")
        self.value.setMinimumWidth(0)
        for label in (self.caption, self.value):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        column = QVBoxLayout(self)
        column.setContentsMargins(16, 10, 16, 10)
        column.setSpacing(2)
        column.addWidget(self.caption)
        column.addWidget(self.value)
        self.setMinimumHeight(64)

    def set_texts(self, caption: str, value: str) -> None:
        self.caption.setText(caption)
        self._full_value = value
        self.setToolTip(value)
        self.setAccessibleName(f"{caption}: {value}")
        self._elide()

    def resizeEvent(self, event: object) -> None:  # noqa: N802
        super().resizeEvent(event)  # type: ignore[arg-type]
        self._elide()

    def _elide(self) -> None:
        from PySide6.QtGui import QFontMetrics

        text = getattr(self, "_full_value", "")
        width = max(20, self.width() - 32)
        self.value.setText(
            QFontMetrics(self.value.font()).elidedText(text, Qt.TextElideMode.ElideRight, width)
        )


class ToolsPage(QWidget):
    """Title, search and the grid of tool cards for one category or all tools."""

    def __init__(self, context: AppContext, tools: list[ToolSpec], open_tool: object) -> None:
        super().__init__()
        self.setObjectName("PageBody")
        self._context = context
        self._tools = tools
        self._open_tool = open_tool
        self._category: str = ALL
        self._cards: list[ToolCard] = []
        self._columns = 0

        self.title = QLabel()
        self.title.setProperty("textStyle", "display")
        self.subtitle = QLabel()
        self.subtitle.setProperty("textStyle", "secondary")
        heading = QVBoxLayout()
        heading.setSpacing(4)
        heading.addWidget(self.title)
        heading.addWidget(self.subtitle)

        self.search = SearchField(context.theme)
        self.search.setFixedWidth(300)
        self.search.textChanged.connect(self.rebuild)
        self.search.installEventFilter(self)

        header = QHBoxLayout()
        header.setSpacing(16)
        header.addLayout(heading, 1)
        header.addWidget(self.search, 0, Qt.AlignmentFlag.AlignBottom)

        self.grid_host = QWidget()
        self.grid_host.setObjectName("PageBody")
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(8)
        self.grid.setVerticalSpacing(8)

        self.summary = QWidget()
        self.summary.setObjectName("PageBody")
        summary_row = QHBoxLayout(self.summary)
        summary_row.setContentsMargins(0, 0, 0, 12)
        summary_row.setSpacing(8)
        self.stat_tasks = StatCell()
        self.stat_reminder = StatCell()
        self.stat_timer = StatCell()
        self.stat_notes = StatCell()
        for cell, tool in (
            (self.stat_tasks, "tasks"),
            (self.stat_reminder, "reminders"),
            (self.stat_timer, "time_tracker"),
            (self.stat_notes, "notes"),
        ):
            cell.clicked.connect(lambda _=False, t=tool: self._open_by_id(t))
            summary_row.addWidget(cell, 1)
        self._summary_timer = QTimer(self)
        self._summary_timer.timeout.connect(self.refresh_summary)
        self._summary_timer.start(30_000)

        self.notes_label = QLabel()
        self.notes_label.setProperty("textStyle", "section")
        self.notes_list = QListWidget()
        self.notes_list.setMaximumHeight(200)
        self.notes_list.itemActivated.connect(self._open_note)
        self.notes_list.itemClicked.connect(self._open_note)

        self.empty = QLabel()
        self.empty.setProperty("textStyle", "empty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.empty.setWordWrap(True)

        body = QWidget()
        body.setObjectName("PageBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addWidget(self.summary)
        body_layout.addWidget(self.grid_host)
        body_layout.addSpacing(16)
        body_layout.addWidget(self.notes_label)
        body_layout.addWidget(self.notes_list)
        body_layout.addWidget(self.empty)
        body_layout.addStretch(1)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("PageScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setWidget(body)

        layout = page_layout(self)
        layout.addLayout(header)
        layout.addSpacing(20)
        layout.addWidget(self.scroll_area, 1)

    # -- state ---------------------------------------------------------------------------

    def set_category(self, category: str) -> None:
        self._category = category
        self.rebuild()

    def visible_tool_ids(self) -> list[str]:
        return [card.property("toolId") for card in self._cards]

    def cards(self) -> list[ToolCard]:
        return list(self._cards)

    def _visible_specs(self) -> list[ToolSpec]:
        query = self.search.text().strip()
        specs = [s for s in self._tools if matches(s, query)]
        if self._category != ALL and not query:
            specs = [s for s in specs if s.category.value == self._category]
        return specs

    # -- texts ---------------------------------------------------------------------------

    def retranslate(self) -> None:
        self.search.setPlaceholderText(tr("overview.search.placeholder"))
        self.search.setAccessibleName(tr("overview.search.placeholder"))
        self.search.set_hint(tr("overview.search.hint"))
        self.rebuild()

    def _update_heading(self) -> None:
        query = self.search.text().strip()
        if query:
            self.title.setText(tr("overview.results", query=query))
            self.subtitle.setText(tr("overview.results.subtitle"))
        elif self._category == ALL:
            self.title.setText(tr("nav.all"))
            self.subtitle.setText(tr("page.all.subtitle"))
        else:
            self.title.setText(tr(f"category.{self._category}"))
            self.subtitle.setText(tr(f"page.{self._category}.subtitle"))

    # -- grid ----------------------------------------------------------------------------

    def _open_by_id(self, tool_id: str) -> None:
        spec = next((s for s in self._tools if s.id == tool_id), None)
        if spec is not None:
            self._open_tool(spec)  # type: ignore[operator]

    def _open_note(self, entry: QListWidgetItem) -> None:
        from desktop_organizer.app import launcher

        launcher.launch_tool("notes", ["--message", f"open:{entry.data(Qt.ItemDataRole.UserRole)}"])

    def refresh_summary(self) -> None:
        """Today strip: open tasks, next reminder, running timer, number of notes."""
        lang = self._context.translator.language
        conn = self._context.database.connection
        try:
            from desktop_organizer.tools.reminders.logic import next_upcoming
            from desktop_organizer.tools.tasks.logic import counts
            from desktop_organizer.tools.time_tracker.logic import running

            task_counts = counts(conn)
            reminder = next_upcoming(conn)
            timer = running(conn)
            notes = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        except Exception:  # noqa: BLE001 - e.g. database closed after "Delete all data"
            return
        self.stat_tasks.set_texts(
            tr("overview.today.tasks"),
            tr("overview.today.tasks.value", open=task_counts["open"], today=task_counts["today"]),
        )
        self.stat_reminder.set_texts(
            tr("overview.today.reminder"),
            f"{self._short_time(reminder.due, lang)} · {reminder.title}"
            if reminder
            else tr("overview.today.none"),
        )
        self.stat_timer.set_texts(
            tr("overview.today.timer"),
            tr(
                "overview.today.timer.running",
                project=timer.project,
                elapsed=format_duration(timer.duration()),
            )
            if timer
            else tr("overview.today.timer.idle"),
        )
        self.stat_notes.set_texts(
            tr("overview.today.notes"), tr("overview.today.notes.value", count=notes)
        )

    @staticmethod
    def _short_time(timestamp: float, lang: str) -> str:
        from datetime import date, datetime

        moment = datetime.fromtimestamp(timestamp)
        if moment.date() == date.today():
            return moment.strftime("%H:%M")
        return format_datetime(timestamp, lang)

    def _search_notes(self, query: str) -> None:
        self.notes_list.clear()
        found = []
        if query:
            try:
                from desktop_organizer.tools.notes.logic import search

                found = search(self._context.database.connection, query, limit=6)
            except Exception:  # noqa: BLE001
                found = []
        for note in found:
            entry = QListWidgetItem(
                self._context.theme.icon("notebook-pen", secondary=True), note.display_title or "…"
            )
            entry.setData(Qt.ItemDataRole.UserRole, note.id)
            entry.setToolTip(tr("overview.note_open"))
            self.notes_list.addItem(entry)
        self.notes_label.setText(tr("overview.notes_results"))
        self.notes_label.setVisible(bool(found))
        self.notes_list.setVisible(bool(found))
        self.notes_list.setFixedHeight(min(200, 40 * len(found) + 8))

    def rebuild(self) -> None:
        self._update_heading()
        query = self.search.text().strip()
        self.summary.setVisible(self._category == ALL and not query)
        if self.summary.isVisibleTo(self):
            self.refresh_summary()
        self._search_notes(query)
        focused = next((c.property("toolId") for c in self._cards if c.hasFocus()), None)
        for card in self._cards:
            # Hide and detach at once; deleteLater alone leaves old cards painted
            # until the event loop runs.
            card.hide()
            card.setParent(None)
            card.deleteLater()
        self._cards = []
        for spec in self._visible_specs():
            card = ToolCard(
                self._context.theme,
                spec.icon,
                spec.available,
                lambda: tr("overview.badge.planned"),
            )
            card.setProperty("toolId", spec.id)
            card.setText(tr(spec.title_key))
            description = tr(spec.description_key)
            card.set_description(description)
            card.setToolTip(
                description
                if spec.available
                else f"{description}\n{tr('overview.not_available.tooltip')}"
            )
            card.setAccessibleName(tr(spec.title_key))
            card.setAccessibleDescription(
                description if spec.available else f"{description} {tr('overview.not_available')}."
            )
            card.clicked.connect(lambda _=False, s=spec: self._open_tool(s))  # type: ignore[operator]
            card.arrow_pressed.connect(self._move_focus)
            self._cards.append(card)
            if spec.id == focused:
                QTimer.singleShot(0, card.setFocus)
        self.empty.setText(tr("overview.empty", query=self.search.text().strip()))
        self.empty.setVisible(not self._cards and not self.notes_list.count())
        self._columns = 0
        self._layout_grid()

    def _column_count(self) -> int:
        return 2 if self.scroll_area.viewport().width() >= TWO_COLUMN_MIN_WIDTH else 1

    def _layout_grid(self) -> None:
        columns = self._column_count()
        if columns == self._columns and all(self.grid.indexOf(c) >= 0 for c in self._cards):
            return
        self._columns = columns
        while self.grid.count():
            self.grid.takeAt(0)
        for index, card in enumerate(self._cards):
            self.grid.addWidget(card, index // columns, index % columns)
        for column in range(2):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)

    def resizeEvent(self, event: object) -> None:  # noqa: N802
        super().resizeEvent(event)  # type: ignore[arg-type]
        self._layout_grid()

    def focus_first_card(self) -> None:
        if self._cards:
            self._cards[0].setFocus(Qt.FocusReason.TabFocusReason)

    def _move_focus(self, direction: str) -> None:
        current = next((i for i, c in enumerate(self._cards) if c.hasFocus()), None)
        if current is None:
            return
        cols = max(self._columns, 1)
        step = {"left": -1, "right": 1, "up": -cols, "down": cols}[direction]
        target = current + step
        if direction == "up" and target < 0:
            self.search.setFocus()
            return
        if 0 <= target < len(self._cards):
            card = self._cards[target]
            card.setFocus(Qt.FocusReason.TabFocusReason)
            self.scroll_area.ensureWidgetVisible(card, 0, 16)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self.search and isinstance(event, QKeyEvent):
            if event.type() != QEvent.Type.KeyPress:
                return False
            if event.key() == Qt.Key.Key_Down:
                self.focus_first_card()
                return True
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._cards:
                self._cards[0].click()
                return True
            if event.key() == Qt.Key.Key_Escape and self.search.text():
                self.search.clear()
                return True
        return super().eventFilter(watched, event)


class OverviewWindow(QMainWindow):
    def __init__(self, context: AppContext, tools: list[ToolSpec]) -> None:
        super().__init__()
        self._context = context
        self._tools = tools
        self.services: object = None
        self.setMinimumSize(760, 520)

        # Sidebar ----------------------------------------------------------------------
        self.logo = QLabel()
        self.app_name = QLabel()
        self.app_name.setProperty("textStyle", "appName")
        brand = QHBoxLayout()
        brand.setContentsMargins(12, 4, 12, 4)
        brand.setSpacing(10)
        brand.addWidget(self.logo)
        brand.addWidget(self.app_name, 1)

        self.nav_group = QButtonGroup(self)
        self.nav_all = NavButton(context.theme, "layout-grid")
        self.nav_categories: dict[str, NavButton] = {}
        icons = {
            Category.FILES: "folder-open",
            Category.SAFETY: "shield-check",
            Category.EVERYDAY: "calendar-check",
            Category.SYSTEM: "gauge",
        }
        nav = QVBoxLayout()
        nav.setSpacing(2)
        nav.addWidget(self.nav_all)
        self.nav_group.addButton(self.nav_all)
        self.nav_all.clicked.connect(lambda: self._show_tools(ALL))
        for category in CATEGORY_ORDER:
            button = NavButton(context.theme, icons[category])
            button.set_count(sum(1 for t in tools if t.category is category))
            button.clicked.connect(lambda _=False, c=category.value: self._show_tools(c))
            self.nav_group.addButton(button)
            self.nav_categories[category.value] = button
            nav.addWidget(button)
        self.nav_all.set_count(len(tools))

        self.nav_settings = NavButton(context.theme, "settings")
        self.nav_group.addButton(self.nav_settings)
        self.nav_settings.clicked.connect(self.show_settings)

        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(248)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(8, 16, 8, 12)
        side.setSpacing(0)
        side.addLayout(brand)
        side.addSpacing(20)
        side.addLayout(nav)
        side.addStretch(1)
        side.addWidget(self.nav_settings)

        # Content ----------------------------------------------------------------------
        self.tools_page = ToolsPage(context, tools, self.open_tool)
        self.settings_page = SettingsPage(context)
        self.pages = QStackedWidget()
        self.pages.setObjectName("PageBody")
        self.pages.addWidget(self.tools_page)
        self.pages.addWidget(self.settings_page)

        self.meter_cpu = Meter(context.theme)
        self.meter_memory = Meter(context.theme)
        self.meter_battery = Meter(context.theme)
        self.version_label = QLabel()
        self.version_label.setProperty("textStyle", "caption")
        status = QWidget()
        status.setObjectName("StatusLine")
        status_layout = QHBoxLayout(status)
        status_layout.setContentsMargins(32, 8, 32, 8)
        status_layout.setSpacing(24)
        status_layout.addWidget(self.meter_cpu)
        status_layout.addWidget(self.meter_memory)
        status_layout.addWidget(self.meter_battery)
        status_layout.addStretch(1)
        status_layout.addWidget(self.version_label)

        layer = QFrame()
        layer.setObjectName("Layer")
        layer_layout = QVBoxLayout(layer)
        layer_layout.setContentsMargins(0, 0, 0, 0)
        layer_layout.setSpacing(0)
        layer_layout.addWidget(self.pages, 1)
        layer_layout.addWidget(status)

        central = QWidget()
        central.setObjectName("Sidebar")
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(sidebar)
        root.addWidget(layer, 1)
        self.setCentralWidget(central)

        # Behavior ---------------------------------------------------------------------
        for key in ("Ctrl+K", QKeySequence.StandardKey.Find):
            dialogs.shortcut(key, self, self._focus_search)
        dialogs.shortcut("Ctrl+,", self, self.show_settings)

        system_info.prime()
        self._timer = QTimer(self)
        self._timer.setInterval(STATUS_INTERVAL_MS)
        self._timer.timeout.connect(self._update_status)
        self._timer.start()

        context.translator.subscribe(self.retranslate)
        context.theme.on_change(self._on_theme_change)
        self._restore_geometry()
        self._on_theme_change()
        self.nav_all.setChecked(True)
        self.retranslate()

    # -- compatibility helpers used by tests and the smoke test --------------------------

    @property
    def search(self) -> SearchField:
        return self.tools_page.search

    def visible_tool_ids(self) -> list[str]:
        return self.tools_page.visible_tool_ids()

    # -- texts and theme -----------------------------------------------------------------

    def retranslate(self) -> None:
        self.setWindowTitle(tr("app.name"))
        self.app_name.setText(tr("app.name"))
        self.nav_all.setText(tr("nav.all"))
        self.nav_all.setAccessibleName(tr("nav.all"))
        for category, button in self.nav_categories.items():
            button.setText(tr(f"category.{category}"))
            button.setAccessibleName(tr(f"category.{category}"))
        self.nav_settings.setText(tr("overview.settings"))
        self.nav_settings.setAccessibleName(tr("overview.settings"))
        self.nav_settings.setToolTip(f"{tr('overview.settings')} (Ctrl+,)")
        self.version_label.setText(tr("settings.about.version", version=__version__))
        self.tools_page.retranslate()
        self._update_status()

    def _on_theme_change(self) -> None:
        logo = QPixmap(str(resources_dir() / "app-24.png"))
        logo.setDevicePixelRatio(2.0)
        self.logo.setPixmap(logo)
        painted: list[QWidget] = [
            *self.findChildren(NavButton),
            *self.findChildren(ToolCard),
            *self.findChildren(Meter),
        ]
        for widget in painted:
            widget.update()

    # -- navigation ----------------------------------------------------------------------

    def _show_tools(self, category: str) -> None:
        self.pages.setCurrentWidget(self.tools_page)
        if category != ALL and self.tools_page.search.text():
            self.tools_page.search.blockSignals(True)
            self.tools_page.search.clear()
            self.tools_page.search.blockSignals(False)
        self.tools_page.set_category(category)

    def show_settings(self) -> None:
        self.nav_settings.setChecked(True)
        self.pages.setCurrentWidget(self.settings_page)

    def show_category(self, category: str) -> None:
        button = self.nav_all if category == ALL else self.nav_categories[category]
        button.setChecked(True)
        self._show_tools(category)

    def _focus_search(self) -> None:
        if self.pages.currentWidget() is not self.tools_page:
            self.show_category(ALL)
        self.search.setFocus()
        self.search.selectAll()

    def open_tool(self, spec: ToolSpec) -> None:
        if spec.factory is not None:
            self.launch(spec.id)

    def launch(self, tool_id: str, extra: list[str] | None = None) -> bool:
        """Start the tool as its own process; a running copy comes to the front instead."""
        from desktop_organizer.app import launcher

        if tool_id not in {t.id for t in self._tools}:
            return False
        if not launcher.launch_tool(tool_id, extra):
            dialogs.warn(
                self,
                tr("app.name"),
                tr("overview.launch_failed", tool=tr(f"tool.{tool_id}.title")),
            )
            return False
        recent = [tool_id, *[t for t in self._context.settings.get("recent_tools") if t != tool_id]]
        self._context.settings.set("recent_tools", recent[:6])
        return True

    def bring_to_front(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    # -- status line ---------------------------------------------------------------------

    def _update_status(self) -> None:
        lang = self._context.translator.language
        try:
            snap = system_info.snapshot()
        except Exception:
            log.exception("Reading system information failed")
            return
        self.meter_cpu.set_reading(
            tr("status.cpu.label"), format_percent(snap.cpu_percent, lang), snap.cpu_percent / 100
        )
        self.meter_memory.set_reading(
            tr("status.memory.label"),
            tr(
                "status.memory.value",
                used=format_bytes(snap.memory_used, lang),
                total=format_bytes(snap.memory_total, lang),
            ),
            snap.memory_used / snap.memory_total if snap.memory_total else None,
        )
        if snap.battery_percent is None:
            self.meter_battery.hide()
        else:
            value = format_percent(snap.battery_percent, lang)
            if snap.battery_charging:
                value = tr("status.battery.charging", value=value)
            self.meter_battery.set_reading(
                tr("status.battery.label"), value, snap.battery_percent / 100
            )
            self.meter_battery.show()

    # -- window state --------------------------------------------------------------------

    def _restore_geometry(self) -> None:
        saved = self._context.settings.get("window_geometry").get("overview")
        if isinstance(saved, str):
            self.restoreGeometry(QByteArray.fromBase64(saved.encode("ascii")))
        else:
            self.resize(1080, 720)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        geometry = dict(self._context.settings.get("window_geometry"))
        geometry["overview"] = bytes(self.saveGeometry().toBase64().data()).decode("ascii")
        self._context.settings.set("window_geometry", geometry)
        services = self.services
        if self._context.settings.get("run_in_background") and services is not None:
            # Keep running in the notification area (reminders, clipboard, shortcuts).
            event.ignore()
            self.hide()
            services.window_closed_to_background()  # type: ignore[attr-defined]
            return
        self._timer.stop()
        super().closeEvent(event)
        QApplication.quit()
