import pytest

from desktop_organizer.core.formatting import format_bytes, format_number, format_percent


@pytest.mark.parametrize(
    ("size", "lang", "expected"),
    [
        (0, "en", "0 B"),
        (1023, "en", "1,023 B"),
        (1024, "en", "1 KB"),
        (int(8.1 * 1024**3), "en", "8.1 GB"),
        (int(8.1 * 1024**3), "de", "8,1 GB"),
        (512 * 1024**3, "en", "512 GB"),
        (3 * 1024**5, "en", "3,072 TB"),
    ],
)
def test_format_bytes(size: int, lang: str, expected: str) -> None:
    assert format_bytes(size, lang) == expected


def test_format_number_german_separators() -> None:
    assert format_number(1234567.891, "de", 2) == "1.234.567,89"
    assert format_number(1234567.891, "en", 2) == "1,234,567.89"


def test_format_percent() -> None:
    assert format_percent(12.4, "en") == "12%"
    assert format_percent(12.6, "de") == "13\u00a0%"
