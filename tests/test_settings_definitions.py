import pytest

from greentechhub_core.settings import Setting, SettingScope, SettingType


def _setting(**overrides) -> Setting:
    fields = {
        "key": "ui.page_size",
        "type": SettingType.INT,
        "default": 25,
        "scope": SettingScope.USER,
        "label": "Rows per page",
    }
    return Setting(**(fields | overrides))


# construction


@pytest.mark.parametrize("key", ["ui", "ui.page_size", "a1.b_2.c3"])
def test_well_formed_keys_are_accepted(key):
    assert _setting(key=key).key == key


@pytest.mark.parametrize(
    "key", ["", "UI.theme", "ui..theme", ".ui", "ui.", "ui.page__size", "_ui", "ui-x"]
)
def test_malformed_keys_are_rejected(key):
    with pytest.raises(ValueError, match="invalid setting key"):
        _setting(key=key)


def test_plain_strings_are_coerced_to_the_enums():
    setting = _setting(type="int", scope="app")
    assert setting.type is SettingType.INT
    assert setting.scope is SettingScope.APP


def test_choices_accept_a_mapping_bare_values_or_pairs_in_order():
    by_map = _setting(type=SettingType.CHOICE, default="b", choices={"b": "Bee", "a": "Ay"})
    by_values = _setting(type=SettingType.CHOICE, default="b", choices=["b", "a"])
    by_pairs = _setting(type=SettingType.CHOICE, default="b", choices=[("b", "Bee"), ("a", "Ay")])
    assert by_map.choices == by_pairs.choices == (("b", "Bee"), ("a", "Ay"))
    assert by_values.choices == (("b", "b"), ("a", "a"))
    assert by_map.choice_values == ("b", "a")


def test_a_choice_setting_needs_choices():
    with pytest.raises(ValueError, match="needs choices"):
        _setting(type=SettingType.CHOICE, default="a")


def test_duplicate_choice_values_are_rejected():
    with pytest.raises(ValueError, match="duplicate choice"):
        _setting(type=SettingType.CHOICE, default="a", choices=["a", ("a", "Again")])


def test_only_a_choice_setting_takes_choices():
    with pytest.raises(ValueError, match="only a choice setting"):
        _setting(choices=["a"])


def test_only_an_int_setting_takes_bounds():
    with pytest.raises(ValueError, match="only an int setting"):
        _setting(type=SettingType.STR, default="x", min=1)


def test_min_above_max_is_rejected():
    with pytest.raises(ValueError, match="above max"):
        _setting(min=10, max=5)


def test_an_invalid_default_is_rejected_at_definition_time():
    with pytest.raises(ValueError, match="invalid default"):
        _setting(default=500, max=200)


def test_is_frozen():
    with pytest.raises(AttributeError):
        _setting().default = 10


# validate


@pytest.mark.parametrize(
    ("overrides", "value"),
    [
        ({"type": SettingType.BOOL, "default": False}, True),
        ({"min": 5, "max": 200}, 5),
        ({"min": 5, "max": 200}, 200),
        ({"type": SettingType.STR, "default": ""}, "anything"),
        ({"type": SettingType.CHOICE, "default": "a", "choices": ["a", "b"]}, "b"),
    ],
)
def test_validate_returns_valid_values_unchanged(overrides, value):
    assert _setting(**overrides).validate(value) == value


@pytest.mark.parametrize(
    ("overrides", "value"),
    [
        ({"type": SettingType.BOOL, "default": False}, 1),
        ({"type": SettingType.BOOL, "default": False}, "true"),
        ({}, "5"),
        ({}, True),
        ({}, 5.0),
        ({"min": 5}, 4),
        ({"max": 200}, 201),
        ({"type": SettingType.STR, "default": ""}, 5),
        ({"type": SettingType.CHOICE, "default": "a", "choices": ["a"]}, "z"),
    ],
)
def test_validate_rejects_wrong_types_and_out_of_range_values(overrides, value):
    with pytest.raises(ValueError):
        _setting(**overrides).validate(value)


# coerce


@pytest.mark.parametrize(
    ("raw", "expected"), [("true", True), (" ON ", True), ("0", False), ("No", False)]
)
def test_coerce_bool(raw, expected):
    assert _setting(type=SettingType.BOOL, default=False).coerce(raw) is expected


def test_coerce_bool_rejects_other_strings():
    with pytest.raises(ValueError, match="yes/no"):
        _setting(type=SettingType.BOOL, default=False).coerce("maybe")


def test_coerce_int_parses_and_checks_bounds():
    setting = _setting(min=5, max=200)
    assert setting.coerce(" 50 ") == 50
    with pytest.raises(ValueError, match="whole number"):
        setting.coerce("fifty")
    with pytest.raises(ValueError, match="above the maximum"):
        setting.coerce("500")


def test_coerce_str_and_choice_take_the_string_as_given():
    assert _setting(type=SettingType.STR, default="").coerce(" hi ") == " hi "
    choice = _setting(type=SettingType.CHOICE, default="a", choices=["a", "b"])
    assert choice.coerce("b") == "b"
    with pytest.raises(ValueError):
        choice.coerce("c")
