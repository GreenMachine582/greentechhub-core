"""settings.builtins — opt-in, shared user preferences — see
docs/settings.md.

Nothing here is registered anywhere on import. A service that wants these
passes them to its own registry:

    registry = SettingsRegistry(USER_PREFERENCES)

or registers a subset. The keys are shared so greentechhub-ui can honour
them across every service (theme, dates, tables) without per-service
wiring.
"""

import zoneinfo

from greentechhub_core.settings.definitions import Setting, SettingScope, SettingType

THEME = Setting(
    key="ui.theme",
    type=SettingType.CHOICE,
    default="system",
    scope=SettingScope.USER,
    label="Theme",
    help_text="Light, dark, or follow your device.",
    choices={"light": "Light", "dark": "Dark", "system": "System"},
    group="Appearance",
)

TIMEZONE = Setting(
    key="locale.timezone",
    type=SettingType.CHOICE,
    default="UTC",
    scope=SettingScope.USER,
    label="Timezone",
    help_text="Dates and times are shown in this timezone.",
    # IANA names from the host's tz database; UTC is always offered so the
    # default stays valid on a host without one (e.g. Windows without tzdata).
    choices=sorted(zoneinfo.available_timezones() | {"UTC"}),
    group="Locale",
)

DATE_FORMAT = Setting(
    key="locale.date_format",
    type=SettingType.CHOICE,
    default="iso",
    scope=SettingScope.USER,
    label="Date format",
    choices={
        "iso": "2026-01-31",
        "dmy": "31/01/2026",
        "mdy": "01/31/2026",
        "long": "31 Jan 2026",
    },
    group="Locale",
)

PAGE_SIZE = Setting(
    key="ui.page_size",
    type=SettingType.INT,
    default=25,
    scope=SettingScope.USER,
    label="Rows per page",
    help_text="How many rows a table shows per page.",
    min=5,
    max=200,
    group="Tables",
)

USER_PREFERENCES: tuple[Setting, ...] = (THEME, TIMEZONE, DATE_FORMAT, PAGE_SIZE)
