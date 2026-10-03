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

landing_page_setting is a factory rather than a constant, and isn't in
USER_PREFERENCES: its choices are the service's own pages, so the service
builds it and registers it alongside the rest.

site_banner_settings is the same kind of factory for an APP-scope pair: a
site-wide banner message and its tone, which an adapter turns into
greentechhub-ui's `site_banners` (rendered above the navbar on every page).
The edit permission is the service's own, so it's a parameter.
"""

import zoneinfo
from collections.abc import Iterable, Mapping

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

LANDING_PAGE_KEY = "ui.landing_page"
"""The key landing_page_setting registers under, for an adapter's redirect
(or anything else) to read."""


def landing_page_setting(
    choices: Mapping[str, str] | Iterable[str] | Iterable[tuple[str, str]],
    *,
    default: str,
    label: str = "Landing page",
    help_text: str = "The page you see after signing in.",
) -> Setting:
    """A USER choice setting for the page each person lands on, keyed
    LANDING_PAGE_KEY in the Navigation group.

    `choices` are the service's own pages, url → label, in any form Setting
    accepts (a mapping, (url, label) pairs, or bare urls). `default` must be
    one of them; Setting raises ValueError otherwise, or for empty choices.
    Acting on the value (redirecting) is the adapter's or service's job.
    """
    return Setting(
        key=LANDING_PAGE_KEY,
        type=SettingType.CHOICE,
        default=default,
        scope=SettingScope.USER,
        label=label,
        help_text=help_text,
        choices=choices,
        group="Navigation",
    )


SITE_BANNER_KEY = "site.banner"
"""The banner message key: empty means no banner."""

SITE_BANNER_TONE_KEY = "site.banner_tone"
"""The banner tone key: one of greentechhub-ui's gth_alert_banner tones."""

SITE_BANNER_TONES = {
    "info": "Info",
    "warn": "Warning",
    "bad": "Alert",
    "good": "Success",
    "neutral": "Neutral",
}
"""gth_alert_banner's tones, value → label, in the order an editor offers them."""


def site_banner_settings(
    *, edit_permission: str | None = None, group: str = "Site"
) -> tuple[Setting, Setting]:
    """An APP-scope site banner: the message (SITE_BANNER_KEY, empty for
    none) and its tone (SITE_BANNER_TONE_KEY, default "warn").

    `edit_permission` gates changing them, e.g. the service's own
    "settings.manage"; None leaves that to the registry's caller. Showing
    the banner (turning the resolved values into greentechhub-ui's
    `site_banners`) is the adapter's or service's job.
    """
    return (
        Setting(
            key=SITE_BANNER_KEY,
            type=SettingType.STR,
            default="",
            scope=SettingScope.APP,
            label="Site banner",
            help_text="Shown to everyone above the navbar, e.g. planned maintenance. "
            "Leave empty for none.",
            group=group,
            edit_permission=edit_permission,
        ),
        Setting(
            key=SITE_BANNER_TONE_KEY,
            type=SettingType.CHOICE,
            default="warn",
            scope=SettingScope.APP,
            label="Banner style",
            choices=SITE_BANNER_TONES,
            group=group,
            edit_permission=edit_permission,
        ),
    )
