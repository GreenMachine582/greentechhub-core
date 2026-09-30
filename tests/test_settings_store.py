import json

import pytest

from greentechhub_core.settings import JsonFileSettingsStore, SettingScope

APP = SettingScope.APP
USER = SettingScope.USER


def test_a_missing_file_reads_empty_and_is_created_on_first_write(tmp_path):
    path = tmp_path / "nested" / "settings.json"
    store = JsonFileSettingsStore(path)
    assert store.get_many_sync(APP, None) == {}
    assert not path.exists()
    store.set_sync(USER, "alice", "ui.theme", "dark")
    assert json.loads(path.read_text()) == {"app": {}, "user": {"alice": {"ui.theme": "dark"}}}


def test_reads_the_file_on_every_call(tmp_path):
    path = tmp_path / "settings.json"
    store = JsonFileSettingsStore(path)
    path.write_text(json.dumps({"app": {"site.banner": "hi"}}))
    assert store.get_many_sync(APP, None) == {"site.banner": "hi"}
    assert store.get_many_sync(USER, "alice") == {}


def test_two_instances_on_one_file_see_each_others_writes(tmp_path):
    first = JsonFileSettingsStore(tmp_path / "settings.json")
    second = JsonFileSettingsStore(tmp_path / "settings.json")
    first.set_sync(APP, None, "ui.page_size", 50)
    assert second.get_many_sync(APP, None) == {"ui.page_size": 50}


def test_deleting_a_users_last_value_drops_the_subject(tmp_path):
    store = JsonFileSettingsStore(tmp_path / "settings.json")
    store.set_sync(USER, "alice", "ui.theme", "dark")
    store.delete_sync(USER, "alice", "ui.theme")
    assert json.loads(store.path.read_text())["user"] == {}


@pytest.mark.parametrize("content", ["not json", "[]", '{"app": []}', '{"user": {"alice": 1}}'])
def test_a_malformed_file_raises_and_is_left_alone(tmp_path, content):
    path = tmp_path / "settings.json"
    path.write_text(content)
    store = JsonFileSettingsStore(path)
    with pytest.raises(ValueError, match="settings.json"):
        store.set_sync(APP, None, "ui.theme", "dark")
    assert path.read_text() == content


def test_leaves_no_temp_files_behind(tmp_path):
    store = JsonFileSettingsStore(tmp_path / "settings.json")
    store.set_sync(APP, None, "ui.theme", "dark")
    assert [p.name for p in tmp_path.iterdir()] == ["settings.json"]
