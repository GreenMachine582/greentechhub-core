import dataclasses

import pytest

from greentechhub_core.version import (
    VersionInfo,
    get_installed_versions,
    get_package_version,
    get_version_info,
)

# get_package_version


def test_returns_version_of_an_actually_installed_package():
    assert get_package_version("greentechhub-core") == "0.1.0"


def test_returns_none_for_a_package_that_is_not_installed():
    assert get_package_version("definitely-not-a-real-package-xyz123") is None


# get_installed_versions


def test_default_prefix_includes_this_package_at_its_installed_version():
    result = get_installed_versions()
    assert result["greentechhub-core"] == "0.1.0"


def test_prefix_match_is_case_insensitive():
    result = get_installed_versions(prefix="GREENTECHHUB-")
    assert result["greentechhub-core"] == "0.1.0"


def test_implausible_prefix_returns_empty_dict():
    result = get_installed_versions(prefix="definitely-not-a-real-prefix-xyz123-")
    assert result == {}


# get_version_info


def test_combines_supplied_service_version_with_discovered_packages():
    info = get_version_info(service_version="1.2.3")
    assert info.service == "1.2.3"
    assert info.packages["greentechhub-core"] == "0.1.0"


def test_service_defaults_to_none_when_not_supplied():
    info = get_version_info()
    assert info.service is None


# VersionInfo


def test_is_frozen():
    info = VersionInfo(service=None, packages={})
    with pytest.raises(dataclasses.FrozenInstanceError):
        info.service = "9.9.9"


def test_construction_requires_keyword_args():
    with pytest.raises(TypeError):
        VersionInfo(None, {})
