import re
import string
from pathlib import Path

import pytest

from desktop_organizer.core.i18n import (
    SUPPORTED,
    Translator,
    load_catalog,
    resolve_language,
    system_language,
)
from desktop_organizer.core.paths import resources_dir
from desktop_organizer.tools.registry import CATEGORY_ORDER, PLANNED

I18N = resources_dir() / "i18n"


def _placeholders(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_catalogs_have_identical_keys_and_placeholders() -> None:
    de, en = load_catalog(I18N, "de"), load_catalog(I18N, "en")
    assert set(de) == set(en)
    for key in de:
        assert _placeholders(de[key]) == _placeholders(en[key]), key


def test_every_tool_and_category_has_texts() -> None:
    for code in SUPPORTED:
        catalog = load_catalog(I18N, code)
        for spec in PLANNED:
            assert spec.title_key in catalog
            assert spec.description_key in catalog
        for category in CATEGORY_ORDER:
            assert f"category.{category.value}" in catalog


def test_writing_rules() -> None:
    """Design system: no exclamation marks and no emojis in UI text."""
    emoji = re.compile("[\U0001f300-\U0001faff\u2600-\u27bf]")
    for code in SUPPORTED:
        for key, text in load_catalog(I18N, code).items():
            assert "!" not in text, key
            assert not emoji.search(text), key


def test_every_key_used_in_code_exists() -> None:
    catalog = load_catalog(I18N, "en")
    source = Path(resources_dir()).parent
    pattern = re.compile(r"""\btr\(\s*["']([a-z0-9_.]+)["']""")
    used = set()
    for file in source.rglob("*.py"):
        used.update(pattern.findall(file.read_text(encoding="utf-8")))
    assert used, "no tr() calls found"
    missing = sorted(k for k in used if k not in catalog)
    assert missing == []


@pytest.mark.parametrize(
    ("locale", "expected"), [("en_US", "en"), ("en_GB", "en"), ("de_DE", "de"), ("fr_FR", "de")]
)
def test_system_language(locale: str, expected: str) -> None:
    assert system_language(locale) == expected


def test_resolve_language_respects_explicit_choice() -> None:
    assert resolve_language("en", "de_DE") == "en"
    assert resolve_language("system", "en_US") == "en"


def test_translator_formats_and_falls_back(tmp_path: Path) -> None:
    (tmp_path / "de.json").write_text('{"a": "Hallo {name}"}', encoding="utf-8")
    (tmp_path / "en.json").write_text(
        '{"a": "Hello {name}", "b": "Only English"}', encoding="utf-8"
    )
    t = Translator(tmp_path, "de")
    assert t.tr("a", name="X") == "Hallo X"
    assert t.tr("b") == "Only English"
    assert t.tr("missing") == "missing"
    calls: list[int] = []
    t.subscribe(lambda: calls.append(1))
    t.set_language("en")
    t.set_language("en")
    assert calls == [1]
    with pytest.raises(ValueError):
        t.set_language("fr")
