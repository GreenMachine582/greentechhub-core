import dataclasses

import pytest

from greentechhub_core.proxy import (
    ForwardedInfo,
    is_trusted_proxy,
    parse_forwarded_for,
    resolve_client_ip,
    resolve_forwarded,
    resolve_host,
    resolve_scheme,
)

TRUSTED = ["10.0.0.1", "192.168.1.0/24", "::1"]


# is_trusted_proxy


def test_bare_ip_matches_exact_entry():
    assert is_trusted_proxy("10.0.0.1", TRUSTED) is True


def test_ip_within_cidr_range_matches():
    assert is_trusted_proxy("192.168.1.42", TRUSTED) is True


def test_ipv6_address_matches():
    assert is_trusted_proxy("::1", TRUSTED) is True


def test_malformed_ip_is_not_trusted():
    assert is_trusted_proxy("not-an-ip", TRUSTED) is False


def test_ip_outside_every_entry_is_not_trusted():
    assert is_trusted_proxy("8.8.8.8", TRUSTED) is False


def test_empty_trusted_proxies_trusts_nothing():
    assert is_trusted_proxy("10.0.0.1", []) is False


def test_malformed_entry_in_trusted_proxies_is_skipped_not_raised():
    assert is_trusted_proxy("10.0.0.1", ["garbage", "10.0.0.1"]) is True


# parse_forwarded_for


def test_parses_normal_comma_separated_chain():
    assert parse_forwarded_for("1.1.1.1,2.2.2.2,3.3.3.3") == ["1.1.1.1", "2.2.2.2", "3.3.3.3"]


def test_strips_whitespace_around_entries():
    assert parse_forwarded_for(" 1.1.1.1 , 2.2.2.2 ") == ["1.1.1.1", "2.2.2.2"]


def test_empty_string_returns_empty_list():
    assert parse_forwarded_for("") == []


def test_drops_blank_segments_from_stray_commas():
    assert parse_forwarded_for("1.1.1.1,,2.2.2.2,") == ["1.1.1.1", "2.2.2.2"]


# resolve_client_ip


def test_untrusted_remote_addr_ignores_forwarded_for_header_entirely():
    # The anti-spoofing property: an arbitrary client can set X-Forwarded-For to
    # anything, so an untrusted direct connection must never have it believed.
    assert resolve_client_ip("8.8.8.8", "1.2.3.4", TRUSTED) == "8.8.8.8"


def test_trusted_remote_addr_no_forwarded_for_header_returns_remote_addr():
    assert resolve_client_ip("10.0.0.1", None, TRUSTED) == "10.0.0.1"


def test_trusted_remote_addr_empty_forwarded_for_header_returns_remote_addr():
    assert resolve_client_ip("10.0.0.1", "", TRUSTED) == "10.0.0.1"


def test_trusted_remote_addr_fully_trusted_chain_returns_leftmost_original_client():
    # every hop in the chain happens to be trusted itself; nothing to stop at, so
    # the original leftmost claimed client wins.
    chain = "10.0.0.1,192.168.1.5,10.0.0.1"
    assert resolve_client_ip("10.0.0.1", chain, TRUSTED) == "10.0.0.1"


def test_trusted_remote_addr_single_untrusted_hop_returns_that_hop():
    chain = "203.0.113.7,10.0.0.1"
    assert resolve_client_ip("10.0.0.1", chain, TRUSTED) == "203.0.113.7"


def test_trusted_remote_addr_stops_at_untrusted_entry_partway_through_chain():
    # walking from the right: 10.0.0.1 trusted, 203.0.113.99 not trusted -> stop
    # there; the further-left 203.0.113.7 is never reached or trusted.
    chain = "203.0.113.7,203.0.113.99,10.0.0.1"
    assert resolve_client_ip("10.0.0.1", chain, TRUSTED) == "203.0.113.99"


def test_single_entry_untrusted_chain_returns_that_entry():
    assert resolve_client_ip("10.0.0.1", "203.0.113.7", TRUSTED) == "203.0.113.7"


# resolve_scheme


def test_scheme_trusted_remote_addr_and_header_present_is_used():
    assert resolve_scheme("10.0.0.1", "https", TRUSTED) == "https"


def test_scheme_is_lowercased():
    assert resolve_scheme("10.0.0.1", "HTTPS", TRUSTED) == "https"


def test_scheme_untrusted_remote_addr_falls_back_to_default():
    assert resolve_scheme("8.8.8.8", "https", TRUSTED) == "http"


def test_scheme_header_absent_falls_back_to_default():
    assert resolve_scheme("10.0.0.1", None, TRUSTED) == "http"


def test_scheme_custom_default_is_respected():
    assert resolve_scheme("8.8.8.8", "https", TRUSTED, default="https") == "https"


# resolve_host


def test_host_trusted_remote_addr_and_header_present_is_used():
    assert resolve_host("10.0.0.1", "example.com", TRUSTED) == "example.com"


def test_host_untrusted_remote_addr_falls_back_to_default():
    assert resolve_host("8.8.8.8", "evil.example", TRUSTED) is None


def test_host_header_absent_falls_back_to_default():
    result = resolve_host("10.0.0.1", None, TRUSTED, default="fallback.example")
    assert result == "fallback.example"


# resolve_forwarded


def test_resolve_forwarded_end_to_end_with_mixed_case_header_keys():
    headers = {
        "x-forwarded-for": "203.0.113.7, 10.0.0.1",
        "X-FORWARDED-PROTO": "https",
        "X-Forwarded-Host": "app.example.com",
    }
    info = resolve_forwarded(remote_addr="10.0.0.1", headers=headers, trusted_proxies=TRUSTED)
    assert info == ForwardedInfo(client_ip="203.0.113.7", scheme="https", host="app.example.com")


def test_resolve_forwarded_untrusted_remote_addr_ignores_all_headers():
    headers = {
        "X-Forwarded-For": "1.2.3.4",
        "X-Forwarded-Proto": "https",
        "X-Forwarded-Host": "evil.example",
    }
    info = resolve_forwarded(remote_addr="8.8.8.8", headers=headers, trusted_proxies=TRUSTED)
    assert info == ForwardedInfo(client_ip="8.8.8.8", scheme="http", host=None)


def test_forwarded_info_is_frozen():
    info = ForwardedInfo(client_ip="1.1.1.1", scheme="http", host=None)
    with pytest.raises(dataclasses.FrozenInstanceError):
        info.client_ip = "9.9.9.9"


def test_forwarded_info_construction_requires_keyword_args():
    with pytest.raises(TypeError):
        ForwardedInfo("1.1.1.1", "http", None)
