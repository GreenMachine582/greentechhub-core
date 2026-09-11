from greentechhub_core.observability import get_resource_attributes


def test_service_name_is_always_present():
    attributes = get_resource_attributes(service_name="pyfinbot")
    assert attributes["service.name"] == "pyfinbot"


def test_service_version_included_when_supplied():
    attributes = get_resource_attributes(service_name="pyfinbot", service_version="1.2.3")
    assert attributes["service.version"] == "1.2.3"


def test_service_version_omitted_when_not_supplied():
    attributes = get_resource_attributes(service_name="pyfinbot")
    assert "service.version" not in attributes


def test_returns_only_the_two_documented_keys():
    attributes = get_resource_attributes(service_name="pyfinbot", service_version="1.2.3")
    assert set(attributes) == {"service.name", "service.version"}
