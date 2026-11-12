"""Password generator window."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from desktop_organizer.app.context import AppContext
from desktop_organizer.app.theming import ThemeManager
from desktop_organizer.app.tool_window import ToolWindow
from desktop_organizer.core.i18n import tr
from desktop_organizer.tools.password_generator import SETTINGS
from desktop_organizer.tools.password_generator.logic import (
    PassphraseOptions,
    PasswordOptions,
    crack_time_label,
    generate_passphrase,
    generate_password,
    passphrase_entropy,
    password_entropy,
    strength,
)

TOOL = "password_generator"
LEVELS = ("very_weak", "weak", "fair", "strong", "very_strong")


def t(key: str, **kwargs: object) -> str:
    return tr(f"tool.{TOOL}.{key}", **kwargs)


class StrengthBar(QWidget):
    """Five segments filled according to the strength level."""

    def __init__(self, theme: ThemeManager) -> None:
        super().__init__()
        self._theme = theme
        self._level = 0
        self.setFixedHeight(6)

    def set_level(self, level: str) -> None:
        self._level = LEVELS.index(level) + 1
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802
        t_ = self._theme.tokens
        color = {1: t_.error, 2: t_.error, 3: t_.warning, 4: t_.success, 5: t_.success}.get(
            self._level, t_.nav_selected
        )
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        gap = 6
        width = (self.width() - gap * 4) / 5
        for index in range(5):
            p.setBrush(QColor(color if index < self._level else t_.nav_selected))
            p.drawRoundedRect(QRectF(index * (width + gap), 0, width, 6), 3, 3)
        p.end()


class PasswordWindow(ToolWindow):
    tool_id = TOOL
    icon = "key-round"
    settings_fields = SETTINGS

    def __init__(self, context: AppContext) -> None:
        super().__init__(context)
        self._clear_timer = QTimer(self)
        self._clear_timer.setSingleShot(True)
        self._clear_timer.timeout.connect(self._clear_clipboard)
        self._copied_value = ""

        # Result card -------------------------------------------------------------------------
        self.result = QLineEdit()
        self.result.setReadOnly(True)
        font = QFont("Cascadia Mono, Consolas, monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPixelSize(22)
        self.result.setFont(font)
        self.result.setProperty("mono", True)
        self.result.setMinimumHeight(52)
        self.result.setAccessibleName(t("result"))
        self.show_button = QPushButton()
        self.show_button.setCheckable(True)
        self.show_button.toggled.connect(self._toggle_visible)
        self.copy_button = QPushButton()
        self.copy_button.setProperty("role", "primary")
        self.copy_button.clicked.connect(self.copy)
        self.regenerate_button = QPushButton()
        self.regenerate_button.clicked.connect(self.generate)
        self.strength_bar = StrengthBar(context.theme)
        self.strength_label = QLabel()
        self.strength_label.setProperty("textStyle", "secondary")
        card = QFrame()
        card.setObjectName("Panel")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(12)
        result_row = QHBoxLayout()
        result_row.setSpacing(8)
        result_row.addWidget(self.result, 1)
        result_row.addWidget(self.show_button)
        result_row.addWidget(self.regenerate_button)
        result_row.addWidget(self.copy_button)
        card_layout.addLayout(result_row)
        card_layout.addWidget(self.strength_bar)
        card_layout.addWidget(self.strength_label)
        self.content.addWidget(card)

        # Options -------------------------------------------------------------------------------
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(lambda _i: self.generate())
        password_page = QWidget()
        form = QFormLayout(password_page)
        form.setContentsMargins(0, 16, 0, 0)
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(12)
        self.length = QSlider(Qt.Orientation.Horizontal)
        self.length.setRange(4, 128)
        self.length_value = QSpinBox()
        self.length_value.setRange(4, 128)
        self.length_value.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.length_value.setFixedWidth(64)
        self.length.valueChanged.connect(self.length_value.setValue)
        self.length_value.valueChanged.connect(self.length.setValue)
        self.length.valueChanged.connect(lambda _v: self.generate())
        length_row = QHBoxLayout()
        length_row.addWidget(self.length, 1)
        length_row.addWidget(self.length_value)
        self.length_label = QLabel()
        form.addRow(self.length_label, length_row)
        self.lower_box = QCheckBox()
        self.upper_box = QCheckBox()
        self.digits_box = QCheckBox()
        self.symbols_box = QCheckBox()
        self.ambiguous_box = QCheckBox()
        self.require_each = QCheckBox()
        for box in (
            self.lower_box,
            self.upper_box,
            self.digits_box,
            self.symbols_box,
            self.ambiguous_box,
            self.require_each,
        ):
            box.setChecked(True)
            box.toggled.connect(lambda _v: self.generate())
        self.chars_label = QLabel()
        chars = QVBoxLayout()
        chars.setSpacing(8)
        for box in (self.lower_box, self.upper_box, self.digits_box, self.symbols_box):
            chars.addWidget(box)
        form.addRow(self.chars_label, chars)
        self.rules_label = QLabel()
        rules = QVBoxLayout()
        rules.setSpacing(8)
        rules.addWidget(self.ambiguous_box)
        rules.addWidget(self.require_each)
        form.addRow(self.rules_label, rules)

        phrase_page = QWidget()
        phrase_form = QFormLayout(phrase_page)
        phrase_form.setContentsMargins(0, 16, 0, 0)
        phrase_form.setHorizontalSpacing(24)
        phrase_form.setVerticalSpacing(12)
        self.words = QSpinBox()
        self.words.setRange(3, 12)
        self.words.setValue(6)
        self.words.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.words.setFixedWidth(80)
        self.words.valueChanged.connect(lambda _v: self.generate())
        self.separator = QComboBox()
        for value in ("-", ".", "_", " ", ""):
            self.separator.addItem("", value)
        self.separator.currentIndexChanged.connect(lambda _i: self.generate())
        self.capitalize = QCheckBox()
        self.capitalize.setChecked(True)
        self.capitalize.toggled.connect(lambda _v: self.generate())
        self.add_number = QCheckBox()
        self.add_number.setChecked(True)
        self.add_number.toggled.connect(lambda _v: self.generate())
        self.words_label = QLabel()
        self.separator_label = QLabel()
        phrase_form.addRow(self.words_label, self.words)
        phrase_form.addRow(self.separator_label, self.separator)
        phrase_form.addRow("", self.capitalize)
        phrase_form.addRow("", self.add_number)
        self.tabs.addTab(password_page, "")
        self.tabs.addTab(phrase_page, "")

        # Batch -----------------------------------------------------------------------------------
        self.batch_label = QLabel()
        self.batch_label.setProperty("textStyle", "section")
        self.batch_button = QPushButton()
        self.batch_button.clicked.connect(self.generate_batch)
        self.batch = QListWidget()
        self.batch.setProperty("mono", True)
        self.batch.itemDoubleClicked.connect(lambda entry: self._copy_value(entry.text()))
        batch_box = QVBoxLayout()
        batch_head = QHBoxLayout()
        batch_head.addWidget(self.batch_label, 1)
        batch_head.addWidget(self.batch_button)
        batch_box.addLayout(batch_head)
        batch_box.addWidget(self.batch, 1)
        self.batch_hint = QLabel()
        self.batch_hint.setProperty("textStyle", "caption")
        batch_box.addWidget(self.batch_hint)

        lower = QHBoxLayout()
        lower.setSpacing(24)
        lower.addWidget(self.tabs, 3)
        lower.addLayout(batch_box, 2)
        self.content.addLayout(lower, 1)

        self.privacy = QLabel()
        self.privacy.setProperty("textStyle", "caption")
        self.footer.addWidget(self.privacy, 1)

        self.length.setValue(self.option("default_length"))
        self.retranslate()
        self.generate()

    def retranslate(self) -> None:
        self.show_button.setText(t("hide") if self.show_button.isChecked() else t("show"))
        self.copy_button.setText(tr("common.copy"))
        self.regenerate_button.setText(t("regenerate"))
        self.tabs.setTabText(0, t("tab.password"))
        self.tabs.setTabText(1, t("tab.passphrase"))
        self.length_label.setText(t("length"))
        self.chars_label.setText(t("characters"))
        self.rules_label.setText(t("rules"))
        self.lower_box.setText(t("lower"))
        self.upper_box.setText(t("upper"))
        self.digits_box.setText(t("digits"))
        self.symbols_box.setText(t("symbols"))
        self.ambiguous_box.setText(t("ambiguous"))
        self.require_each.setText(t("require_each"))
        self.words_label.setText(t("words"))
        self.separator_label.setText(t("separator"))
        for index, key in enumerate(("dash", "dot", "underscore", "space", "none")):
            self.separator.setItemText(index, t(f"separator.{key}"))
        self.capitalize.setText(t("capitalize"))
        self.add_number.setText(t("add_number"))
        self.batch_label.setText(t("batch"))
        self.batch_button.setText(t("batch.generate", count=self.option("batch_count")))
        self.batch_hint.setText(t("batch.hint"))
        seconds = self.option("clear_clipboard_seconds")
        self.privacy.setText(t("privacy.clear", seconds=seconds) if seconds else t("privacy"))
        self._update_strength()

    # -- generation ------------------------------------------------------------------------

    def _password_options(self) -> PasswordOptions:
        return PasswordOptions(
            length=self.length.value(),
            lower=self.lower_box.isChecked(),
            upper=self.upper_box.isChecked(),
            digits=self.digits_box.isChecked(),
            symbols=self.symbols_box.isChecked(),
            symbol_set=self.option("symbol_set"),
            exclude_ambiguous=self.ambiguous_box.isChecked(),
            require_each=self.require_each.isChecked(),
        )

    def _phrase_options(self) -> PassphraseOptions:
        language = self.option("passphrase_language")
        if language == "ui":
            language = self.context.translator.language
        return PassphraseOptions(
            words=self.words.value(),
            separator=self.separator.currentData() or "",
            capitalize=self.capitalize.isChecked(),
            add_number=self.add_number.isChecked(),
            language=language,
        )

    def _make_one(self) -> str:
        if self.tabs.currentIndex() == 0:
            return generate_password(self._password_options())
        return generate_passphrase(self._phrase_options())

    def generate(self) -> None:
        try:
            value = self._make_one()
        except ValueError:
            self.result.clear()
            self.info.show_message("warning", t("no_characters"))
            self.copy_button.setEnabled(False)
            return
        self.info.hide()
        self.result.setText(value)
        self.copy_button.setEnabled(True)
        self._toggle_visible(self.show_button.isChecked())
        self._update_strength()

    def generate_batch(self) -> None:
        self.batch.clear()
        try:
            for _ in range(self.option("batch_count")):
                self.batch.addItem(self._make_one())
        except ValueError:
            self.info.show_message("warning", t("no_characters"))

    def _update_strength(self) -> None:
        if not hasattr(self, "tabs"):
            return
        if self.tabs.currentIndex() == 0:
            bits = password_entropy(self._password_options())
        else:
            bits = passphrase_entropy(self._phrase_options())
        level = strength(bits)
        self.strength_bar.set_level(level)
        unit, amount = crack_time_label(bits)
        duration = t(f"time.{unit}", amount=amount)
        self.strength_label.setText(
            t("strength", level=t(f"level.{level}"), bits=int(bits), time=duration)
        )

    def _toggle_visible(self, visible: bool) -> None:
        self.show_button.setText(t("hide") if visible else t("show"))
        self.result.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )

    # -- clipboard ---------------------------------------------------------------------------

    def copy(self) -> None:
        self._copy_value(self.result.text())

    def _copy_value(self, value: str) -> None:
        if not value:
            return
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            return
        clipboard.setText(value)
        self._copied_value = value
        seconds = self.option("clear_clipboard_seconds")
        if seconds:
            self._clear_timer.start(seconds * 1000)
            self.info.show_message("success", t("copied.clear", seconds=seconds))
        else:
            self.info.show_message("success", t("copied"))

    def _clear_clipboard(self) -> None:
        clipboard = QGuiApplication.clipboard()
        # Only clear if the clipboard still holds our password, not something newer.
        if clipboard is not None and clipboard.text() == self._copied_value:
            clipboard.clear()
            self.info.show_message("info", t("cleared"))
        self._copied_value = ""

    def settings_changed(self) -> None:
        self.retranslate()

    def closeEvent(self, event: object) -> None:  # noqa: N802
        if self._clear_timer.isActive():
            self._clear_clipboard()
        super().closeEvent(event)  # type: ignore[arg-type]

    def screenshot_prepare(self) -> None:
        self.show_button.setChecked(True)
        self.generate_batch()
