"""security.form_checks — the new-password rules every sign-up, reset and
change-password form applies, with their messages, so each adapter's forms
say the same thing.

password_problem answers which field is wrong ("new" or "confirm") rather
than a form field name: forms name theirs differently (sign-up's
`password` / `password_confirm`, Settings' `new_password` /
`new_password_confirm`), and each maps the answer onto its own.
"""

PASSWORD_TOO_SHORT = "Use at least {min_length} characters."
PASSWORD_UNCHANGED = "Choose a password different from your current one."
PASSWORDS_DIFFER = "The passwords don't match."


def password_problem(
    new: str, confirm: str, *, min_length: int = 8, current: str | None = None
) -> tuple[str, str] | None:
    """The first problem with a new password, as (field, message) where field
    is "new" or "confirm", or None when it's fine. Checked in order: shorter
    than `min_length`; the same as `current` (when given, e.g. a change of
    password); not matching `confirm`."""
    if len(new) < min_length:
        return "new", PASSWORD_TOO_SHORT.format(min_length=min_length)
    if current is not None and new == current:
        return "new", PASSWORD_UNCHANGED
    if new != confirm:
        return "confirm", PASSWORDS_DIFFER
    return None
