"""trusted_proxy — X-Forwarded-* parsing/validation against a trusted-proxy allowlist.

Pure header-dict-in, validated-client-info-out: no assumption about how "headers"
were obtained (WSGI environ, ASGI scope, or any other request representation), and
no assumption that anything upstream of this module has already sanitized header
values beyond ordinary HTTP header parsing (CRLF stripping etc. happens at the
HTTP server/framework layer, below this module). Wiring the result into request
handling (e.g. overwriting a request's client-address attribute) is left entirely
to the consuming service.

The core security property every function here defends: X-Forwarded-* headers are
*advisory claims from whoever sent the request*, not facts — trustworthy only when
the connection came from, and was relayed only through, addresses this service has
explicitly been told to trust. An untrusted direct connection claiming any
X-Forwarded-For/-Proto/-Host value must never have that value believed; see
resolve_client_ip in particular.

X-Forwarded-For entries are assumed to be bare IPs (no brackets, no trailing
:port) — the conventional shape for this header. Bracketed IPv6 or port-suffixed
entries are not normalized/stripped; nothing in this package's own docs promises
that shape, and guessing at intent risks mis-classifying an entry as trusted or
untrusted. If a deployment's proxy ever emits that shape, normalize before calling
in, or extend parse_forwarded_for.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from ipaddress import ip_address, ip_network

_FORWARDED_FOR = "X-Forwarded-For"
_FORWARDED_PROTO = "X-Forwarded-Proto"
_FORWARDED_HOST = "X-Forwarded-Host"


@dataclass(frozen=True, slots=True, kw_only=True)
class ForwardedInfo:
    """The validated result of reconciling X-Forwarded-* headers against remote_addr.

    Fields:
        client_ip: the real client's address — see resolve_client_ip.
        scheme: the scheme the client actually used — see resolve_scheme.
        host: the host the client actually addressed — see resolve_host. None when
            no trusted X-Forwarded-Host was present and no default was supplied.
    """

    client_ip: str
    scheme: str
    host: str | None


def is_trusted_proxy(ip: str, trusted_proxies: Sequence[str]) -> bool:
    """Return whether ``ip`` matches an entry in ``trusted_proxies``.

    Entries may be bare IPs (IPv4 or IPv6) or CIDR ranges — both are handled by
    ``ip_network(entry, strict=False)``, under which a bare IP behaves as a /32
    (IPv4) or /128 (IPv6) network. An empty ``trusted_proxies`` list (the default
    posture: nothing is trusted until explicitly configured) or any unparseable
    ``ip``/entry always yields False rather than raising, so one malformed
    allowlist entry degrades to "don't trust that entry" instead of crashing
    request handling.
    """
    try:
        addr = ip_address(ip)
    except ValueError:
        return False
    for entry in trusted_proxies:
        try:
            network = ip_network(entry, strict=False)
        except ValueError:
            continue
        if addr in network:
            return True
    return False


def parse_forwarded_for(value: str) -> list[str]:
    """Split a comma-separated X-Forwarded-For value into an ordered list.

    Ordered left (original client) to right (the proxy nearest this service), per
    the conventional X-Forwarded-For append semantics: each proxy appends the
    address it received the request from onto the right of the header. Blank
    segments (stray/trailing commas) are dropped; whitespace around each entry is
    stripped.
    """
    return [part.strip() for part in value.split(",") if part.strip()]


def resolve_client_ip(
    remote_addr: str,
    forwarded_for: str | None,
    trusted_proxies: Sequence[str],
) -> str:
    """Resolve the real client IP, defending against X-Forwarded-For spoofing.

    ``remote_addr`` is the address of whoever actually opened the connection to
    this service — the one fact nothing upstream can forge. If that peer isn't a
    trusted proxy, ``forwarded_for`` is never even inspected: an arbitrary client
    could set that header to anything, so it's only meaningful once a trusted
    proxy is known to have relayed (or itself set) it.

    When ``remote_addr`` is trusted, the chain is walked from the nearest hop
    backward (right to left): each entry is trusted-proxy-checked in turn, and the
    walk stops at the first entry that *isn't* itself a trusted proxy — that entry
    is the real client, since it's the first hop nothing downstream can vouch for.
    (Note: that entry is returned as-is even if it isn't a well-formed IP — the
    chain of trust broke there, so this function can't verify anything past it
    either way; validate the return value yourself if you need a guaranteed IP.)
    If every entry in the chain also happens to be a trusted proxy, the leftmost
    (original claimed client) entry is returned. An absent or empty header with a
    trusted ``remote_addr`` falls back to ``remote_addr`` itself.
    """
    if not is_trusted_proxy(remote_addr, trusted_proxies):
        return remote_addr
    chain = parse_forwarded_for(forwarded_for) if forwarded_for else []
    if not chain:
        return remote_addr
    for candidate in reversed(chain):
        if not is_trusted_proxy(candidate, trusted_proxies):
            return candidate
    return chain[0]


def resolve_scheme(
    remote_addr: str,
    forwarded_proto: str | None,
    trusted_proxies: Sequence[str],
    *,
    default: str = "http",
) -> str:
    """Resolve the scheme the client actually used (e.g. behind a TLS-terminating proxy).

    Only trusted when ``remote_addr`` is a trusted proxy and the header is present
    and non-empty; otherwise ``default`` is returned unchanged. The value is
    lowercased (scheme names are case-insensitive per RFC 7230) so callers can
    compare with ``scheme == "https"`` without normalizing it themselves.
    """
    if forwarded_proto and is_trusted_proxy(remote_addr, trusted_proxies):
        return forwarded_proto.strip().lower()
    return default


def resolve_host(
    remote_addr: str,
    forwarded_host: str | None,
    trusted_proxies: Sequence[str],
    *,
    default: str | None = None,
) -> str | None:
    """Resolve the host the client actually addressed (may include a port).

    Only trusted when ``remote_addr`` is a trusted proxy and the header is present
    and non-empty; otherwise ``default`` is returned unchanged. Unlike
    ``resolve_scheme``, the value is not case-normalized — hostnames are
    conventionally already lowercase on the wire, and a caller with a
    case-sensitive comparison need shouldn't have that decision made for them.
    """
    if forwarded_host and is_trusted_proxy(remote_addr, trusted_proxies):
        return forwarded_host.strip()
    return default


def _get_header(headers: Mapping[str, str], name: str) -> str | None:
    """Case-insensitive header lookup.

    ``headers`` is a plain ``Mapping[str, str]`` (this module's "header-dict-in"
    contract) — deliberately not assuming any specific case-insensitive dict type
    is already in hand, since different HTTP stacks expose headers with different
    casing conventions.
    """
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return value
    return None


def resolve_forwarded(
    *,
    remote_addr: str,
    headers: Mapping[str, str],
    trusted_proxies: Sequence[str],
    default_scheme: str = "http",
    default_host: str | None = None,
) -> ForwardedInfo:
    """Resolve client IP, scheme, and host from headers in one call.

    The primary entry point most callers use — header-dict-in, validated
    ``ForwardedInfo``-out. See ``resolve_client_ip``, ``resolve_scheme``, and
    ``resolve_host`` for the per-field trust rules; all three are applied
    consistently against the same ``remote_addr``/``trusted_proxies`` pair.
    """
    return ForwardedInfo(
        client_ip=resolve_client_ip(
            remote_addr, _get_header(headers, _FORWARDED_FOR), trusted_proxies
        ),
        scheme=resolve_scheme(
            remote_addr,
            _get_header(headers, _FORWARDED_PROTO),
            trusted_proxies,
            default=default_scheme,
        ),
        host=resolve_host(
            remote_addr,
            _get_header(headers, _FORWARDED_HOST),
            trusted_proxies,
            default=default_host,
        ),
    )
