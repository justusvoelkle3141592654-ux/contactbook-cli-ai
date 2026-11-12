from desktop_organizer.tools.registry import PLANNED, Category, ToolSpec, all_tools, discover


def test_twelve_planned_tools_with_unique_ids() -> None:
    assert len(PLANNED) == 12
    assert len({s.id for s in PLANNED}) == 12


def test_no_tool_is_marked_available_without_a_window() -> None:
    for spec in all_tools():
        assert spec.available == (spec.factory is not None)


def test_implementation_replaces_planned_entry() -> None:
    impl = ToolSpec("notes", Category.EVERYDAY, "notebook-pen", factory=lambda ctx: None)  # type: ignore[arg-type,return-value]
    tools = all_tools({"notes": impl})
    assert tools[[s.id for s in tools].index("notes")] is impl
    assert len(tools) == 12


def test_tools_are_grouped_by_category() -> None:
    categories = [s.category for s in all_tools()]
    assert categories == sorted(categories, key=[c for c in Category].index)


def test_discover_finds_only_packages_with_spec() -> None:
    assert isinstance(discover(), dict)
