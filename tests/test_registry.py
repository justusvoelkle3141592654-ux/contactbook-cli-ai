from desktop_organizer.tools.registry import (
    CATEGORY_ORDER,
    TOOL_ORDER,
    all_migrations,
    all_tools,
    discover,
)


def test_tools_have_known_unique_ids() -> None:
    ids = [s.id for s in all_tools()]
    assert len(ids) == len(set(ids))
    assert set(ids) <= set(TOOL_ORDER)


def test_every_tool_has_window_language_file_and_icon() -> None:
    from desktop_organizer.core.paths import resources_dir

    for spec in all_tools():
        assert spec.factory is not None, spec.id
        assert spec.i18n_file is not None, spec.id
        assert (resources_dir() / "icons" / f"{spec.icon}.svg").exists(), spec.icon


def test_settings_defaults_are_valid() -> None:
    for spec in all_tools():
        keys = [f.key for f in spec.settings]
        assert len(keys) == len(set(keys)), spec.id
        for field in spec.settings:
            assert field.validate(field.default) == field.default, (spec.id, field.key)


def test_tools_are_grouped_by_category() -> None:
    categories = [s.category for s in all_tools()]
    assert categories == sorted(categories, key=list(CATEGORY_ORDER).index)


def test_migrations_belong_to_their_tool() -> None:
    for spec in all_tools():
        for migration in spec.migrations:
            assert migration.module == spec.id
    assert isinstance(all_migrations(all_tools()), list)


def test_discover_returns_specs() -> None:
    assert set(discover()) == {s.id for s in all_tools()}
