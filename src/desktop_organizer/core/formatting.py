"""Locale-aware number formatting for the two supported languages."""

from __future__ import annotations

_UNITS = ("B", "KB", "MB", "GB", "TB")


def format_number(value: float, language: str, decimals: int = 0) -> str:
    text = f"{value:,.{decimals}f}"
    if language == "de":
        # 1,234.5 -> 1.234,5
        text = text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return text


def format_bytes(size: int, language: str) -> str:
    """Binary units with conventional labels, for example 8.1 GB."""
    value = float(size)
    unit = _UNITS[0]
    for unit in _UNITS:
        if value < 1024 or unit == _UNITS[-1]:
            break
        value /= 1024
    decimals = 0 if unit in ("B", "KB") or value >= 100 else 1
    return f"{format_number(value, language, decimals)} {unit}"


def format_percent(value: float, language: str) -> str:
    sep = " " if language == "de" else ""
    return f"{format_number(value, language)}{sep}%"


def format_datetime(timestamp: float, language: str, with_time: bool = True) -> str:
    from datetime import datetime

    moment = datetime.fromtimestamp(timestamp)
    if language == "de":
        return moment.strftime("%d.%m.%Y %H:%M" if with_time else "%d.%m.%Y")
    return moment.strftime("%Y-%m-%d %H:%M" if with_time else "%Y-%m-%d")


def format_duration(seconds: float) -> str:
    """Elapsed time as H:MM:SS, for example 1:05:09."""
    total = int(round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"
