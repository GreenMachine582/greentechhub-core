"""settings.builtins — opt-in, shared user preferences — see
docs/settings.md.

Nothing here is registered anywhere on import. A service that wants these
passes them to its own registry:

    registry = SettingsRegistry(USER_PREFERENCES)

or registers a subset. The keys are shared so greentechhub-ui can honour
them across every service (theme, density, motion, sidebar, dates, numbers,
tables) without per-service wiring. USER_PREFERENCES may grow as more shared
keys are added; a service that wants a fixed set registers the individual
constants instead.
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

DENSITY = Setting(
    key="ui.density",
    type=SettingType.CHOICE,
    default="comfortable",
    scope=SettingScope.USER,
    label="Density",
    help_text="Compact fits more rows and fields on screen.",
    choices={"comfortable": "Comfortable", "compact": "Compact"},
    group="Appearance",
)

MOTION = Setting(
    key="ui.motion",
    type=SettingType.CHOICE,
    default="system",
    scope=SettingScope.USER,
    label="Motion",
    help_text="Reduce turns off animations and transitions.",
    choices={"system": "Follow device", "reduce": "Reduce", "full": "Full"},
    group="Appearance",
)

SIDEBAR_DEFAULT = Setting(
    key="ui.sidebar_default",
    type=SettingType.CHOICE,
    default="expanded",
    scope=SettingScope.USER,
    label="Sidebar",
    help_text="How the sidebar starts when you open a page.",
    choices={"expanded": "Expanded", "rail": "Icons only"},
    group="Appearance",
)

NUMBER_FORMAT = Setting(
    key="locale.number_format",
    type=SettingType.CHOICE,
    default="comma_dot",
    scope=SettingScope.USER,
    label="Number format",
    choices={"comma_dot": "1,234.56", "dot_comma": "1.234,56", "space_comma": "1 234,56"},
    group="Locale",
)

TIME_FORMAT = Setting(
    key="locale.time_format",
    type=SettingType.CHOICE,
    default="24h",
    scope=SettingScope.USER,
    label="Time format",
    choices={"24h": "13:45", "12h": "1:45 pm"},
    group="Locale",
)

USER_PREFERENCES: tuple[Setting, ...] = (
    THEME,
    TIMEZONE,
    DATE_FORMAT,
    PAGE_SIZE,
    DENSITY,
    MOTION,
    SIDEBAR_DEFAULT,
    NUMBER_FORMAT,
    TIME_FORMAT,
)
