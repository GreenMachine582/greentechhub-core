"""files.folders: list_folders lists subfolders only, hides hidden ones on
request, reports errors instead of raising, and can't escape its roots."""

import os
import sys
from pathlib import Path

import pytest

from greentechhub_core.files import Crumb, Folder, default_roots, list_folders
from greentechhub_core.files import folders as folders_module


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    for name in ("beta", "Alpha", "gamma/inner", ".cache"):
        (tmp_path / name).mkdir(parents=True)
    (tmp_path / "notes.txt").write_text("not a folder")
    return tmp_path.resolve()


def test_lists_only_folders_sorted_case_insensitively(tree: Path):
    listing = list_folders(tree)
    assert listing.error is None and listing.path == str(tree)
    assert [f.name for f in listing.entries] == ["Alpha", "beta", "gamma"]
    assert listing.entries[0] == Folder("Alpha", str(tree / "Alpha"), False)
    assert listing.hidden_count == 1 and not listing.truncated and not listing.at_roots


def test_show_hidden_includes_dot_folders_marked_hidden(tree: Path):
    listing = list_folders(tree, show_hidden=True)
    assert [f.name for f in listing.entries] == [".cache", "Alpha", "beta", "gamma"]
    assert listing.entries[0].hidden and listing.hidden_count == 0


@pytest.mark.skipif(sys.platform != "win32", reason="Windows file attributes")
def test_the_windows_hidden_attribute_counts_as_hidden(tree: Path):
    import ctypes

    secret = tree / "secret"
    secret.mkdir()
    assert ctypes.windll.kernel32.SetFileAttributesW(str(secret), 0x2)
    assert "secret" not in [f.name for f in list_folders(tree).entries]
    shown = {f.name: f for f in list_folders(tree, show_hidden=True).entries}
    assert shown["secret"].hidden


def test_parent_and_breadcrumbs(tree: Path):
    listing = list_folders(tree / "gamma" / "inner")
    assert listing.parent == str(tree / "gamma")
    assert listing.breadcrumbs[-2:] == (Crumb("gamma", str(tree / "gamma")),
                                       Crumb("inner", str(tree / "gamma" / "inner")))
    anchor = str(Path(tree.anchor))
    assert listing.breadcrumbs[0] == Crumb(anchor, anchor)


def test_a_filesystem_root_has_no_parent():
    root = Path(default_roots()[0])
    listing = list_folders(root)
    assert listing.parent is None
    assert listing.breadcrumbs == (Crumb(str(root), str(root)),)


def test_roots_limit_browsing(tree: Path):
    listing = list_folders(tree / "gamma", roots=[tree])
    assert listing.parent == str(tree)
    assert listing.breadcrumbs == (Crumb(str(tree), str(tree)),
                                   Crumb("gamma", str(tree / "gamma")))
    at_root = list_folders(tree, roots=[tree])
    assert at_root.parent is None and at_root.breadcrumbs == (Crumb(str(tree), str(tree)),)
    escaped = list_folders(tree / "gamma" / ".." / "..", roots=[tree])
    assert escaped.error == "outside_roots" and escaped.entries == ()


def test_a_symlink_out_of_the_roots_is_refused(tree: Path, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    try:
        os.symlink(outside, tree / "link", target_is_directory=True)
    except OSError:
        pytest.skip("can't create symlinks here")
    assert list_folders(tree / "link", roots=[tree]).error == "outside_roots"


def test_no_path_lists_the_roots(tree: Path):
    other = tree / "beta"
    listing = list_folders(None, roots=[tree / "gamma", other])
    assert listing.at_roots and listing.parent is None and listing.breadcrumbs == ()
    assert [f.path for f in listing.entries] == sorted(
        [str(tree / "gamma"), str(other)], key=str.casefold)
    one = list_folders("", roots=[tree])  # one root: its folders straight away
    assert one.path == str(tree) and [f.name for f in one.entries] == ["Alpha", "beta", "gamma"]


def test_default_roots_on_windows_are_the_drives(monkeypatch):
    monkeypatch.setattr(folders_module.sys, "platform", "win32")
    monkeypatch.setattr(folders_module.os, "listdrives", lambda: ["D:\\", "C:\\"], raising=False)
    assert default_roots() == ["C:\\", "D:\\"]
    listing = list_folders(None, roots=None)
    assert listing.at_roots and [f.name for f in listing.entries] == ["C:\\", "D:\\"]


def test_default_roots_elsewhere_is_slash(monkeypatch):
    monkeypatch.setattr(folders_module.sys, "platform", "linux")
    assert default_roots() == ["/"]


def test_errors_are_reported_not_raised(tree: Path):
    assert list_folders(tree / "missing").error == "not_found"
    assert list_folders(tree / "notes.txt").error == "not_a_folder"
    assert list_folders("relative/path").error == "invalid"


@pytest.mark.skipif(sys.platform == "win32" or getattr(os, "geteuid", lambda: 1)() == 0,
                    reason="needs POSIX permissions and a non-root user")
def test_an_unreadable_folder_reports_permission_denied(tree: Path):
    locked = tree / "locked"
    locked.mkdir()
    locked.chmod(0)
    try:
        listing = list_folders(locked)
        assert listing.error == "permission_denied" and listing.entries == ()
        assert listing.parent == str(tree)
    finally:
        locked.chmod(0o755)


def test_permission_errors_from_scandir(tree: Path, monkeypatch):
    def refuse(path):
        raise PermissionError(13, "Access is denied")

    monkeypatch.setattr(folders_module.os, "scandir", refuse)
    listing = list_folders(tree / "beta")
    assert listing.error == "permission_denied" and listing.parent == str(tree)


def test_an_unavailable_drive(tree: Path, monkeypatch):
    def not_ready(path):
        raise OSError(21, "The device is not ready")

    monkeypatch.setattr(folders_module.os, "scandir", not_ready)
    assert list_folders(tree).error == "unavailable"


def test_truncates_at_max_entries(tree: Path):
    listing = list_folders(tree, max_entries=2)
    assert [f.name for f in listing.entries] == ["Alpha", "beta"] and listing.truncated
