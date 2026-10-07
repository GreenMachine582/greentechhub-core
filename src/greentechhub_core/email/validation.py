"""email.validation — a form's "is this an email address?" check and its
message, shared by sign-up, the profile section and anything else that
asks for one."""

EMAIL_INVALID = "Enter an email address, like name@example.com."


def email_looks_valid(address: str) -> bool:
    """Whether `address` looks like an email address: one @ with text on both
    sides and no whitespace. A form check, not a delivery guarantee."""
    local, at, domain = address.partition("@")
    return bool(local and at and domain) and "@" not in domain and not any(
        c.isspace() for c in address
    )
