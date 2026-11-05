"""files.folders — list_folders: one folder's subfolders, safely, for a
folder picker ("Choose the library folder"): folders only, drive roots on
Windows, hidden folders on request, and errors reported in the listing
instead of raised.

    listing = list_folders("/srv/music")
    listing.entries      # (Folder(name="Albums", path="/srv/music/Albums", hidden=False), ...)
    listing.breadcrumbs  # (Crumb("/", "/"), Crumb("srv", "/srv"), Crumb("music", "/srv/music"))
    listing.parent       # "/srv"
    list_folders(None)   # the roots: drive letters (C:\\, D:\\) on Windows, "/" elsewhere

`roots` limits browsing to those folders and below: a path outside every
root (through "..", a symlink or a junction, after resolving) gets
error="outside_roots" and no entries. Without `roots` the whole filesystem
the process can read is browsable, which suits a local single-user app,
not a shared server.

It's synchronous and touches the disk: from async code run it through
asyncio.to_thread.
"""

import os
import stat
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

FolderError = str
"""One of "permission_denied", "not_found", "not_a_folder", "unavailable"
(a drive with no disc, a disconnected share), "outside_roots" or "invalid"
(not an absolute path)."""

_HIDDEN_ATTRIBUTES = (getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 2)
                      | getattr(stat, "FILE_ATTRIBUTE_SYSTEM", 4))


@dataclass(frozen=True, slots=True)
class Folder:
    name: str
    path: str
    hidden: bool = False


@dataclass(frozen=True, slots=True)
class Crumb:
    label: str
    path: str


@dataclass(frozen=True, slots=True, kw_only=True)
class FolderListing:
    """One folder's subfolders (or the roots, when `path` is None).

    `parent` is where "up" goes: None at a root, so the picker goes back to
    the roots. `breadcrumbs` run from the root down to `path`. `hidden_count`
    is how many hidden folders were left out. `truncated` says `entries` was
    cut at max_entries. `error` (see FolderError) comes with no entries.
    """

    path: str | None
    parent: str | None = None
    breadcrumbs: tuple[Crumb, ...] = ()
    entries: tuple[Folder, ...] = ()
    hidden_count: int = 0
    truncated: bool = False
    error: FolderError | None = None

    @property
    def at_roots(self) -> bool:
        return self.path is None


def default_roots() -> list[str]:
    """The drive roots on Windows ("C:\\\\", "D:\\\\", ...), else ["/"]."""
    if sys.platform == "win32":
        listdrives = getattr(os, "listdrives", None)
        if listdrives is not None:
            return sorted(listdrives())
        return [f"{letter}:\\" for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                if os.path.exists(f"{letter}:\\")]
    return ["/"]


def _resolve(path: str | os.PathLike[str]) -> Path:
    return Path(path).expanduser().resolve()


def _is_hidden(entry: os.DirEntry[str]) -> bool:
    if entry.name.startswith("."):
        return True
    attributes = 0
    try:
        attributes = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
    except OSError:
        pass
    return bool(attributes & _HIDDEN_ATTRIBUTES)


def _within(path: Path, root: Path) -> bool:
    return path == root or path.is_relative_to(root)


def _crumbs(path: Path, root: Path | None) -> tuple[Crumb, ...]:
    chain = [path, *path.parents]
    if root is not None:
        chain = [p for p in chain if _within(p, root)]
    crumbs = []
    for p in reversed(chain):
        top = p.parent == p or (root is not None and p == root)
        crumbs.append(Crumb(str(p) if top else p.name, str(p)))
    return tuple(crumbs)


def list_folders(
    path: str | os.PathLike[str] | None = None,
    *,
    roots: Iterable[str | os.PathLike[str]] | None = None,
    show_hidden: bool = False,
    max_entries: int = 1000,
) -> FolderListing:
    """List `path`'s subfolders, sorted by name (case-insensitively).

    `path=None` (or "") lists the roots: `roots` when given, else the drive
    roots on Windows; when there's just one root (`/`), it lists that root's
    folders instead. Hidden folders (a leading "." or, on Windows, the hidden
    or system attribute) are left out unless `show_hidden`. Never raises for
    a filesystem problem: the listing's `error` says what went wrong.
    """
    root_paths = [_resolve(r) for r in roots] if roots is not None else None
    candidates = [str(r) for r in root_paths] if root_paths is not None else default_roots()

    if path is None or str(path) == "":
        if len(candidates) != 1:
            return FolderListing(path=None, entries=tuple(
                Folder(c, c) for c in sorted(candidates, key=str.casefold)))
        path = candidates[0]

    raw = Path(path).expanduser()
    if not raw.is_absolute():
        return FolderListing(path=str(path), error="invalid")
    try:
        target = raw.resolve()
    except OSError:
        return FolderListing(path=str(raw), error="unavailable")

    root: Path | None = None
    if root_paths is not None:
        root = next((r for r in root_paths if _within(target, r)), None)
        if root is None:
            return FolderListing(path=str(target), error="outside_roots")

    at_top = target.parent == target or (root is not None and target == root)
    parent = None if at_top else str(target.parent)
    base = FolderListing(path=str(target), parent=parent, breadcrumbs=_crumbs(target, root))

    folders: list[Folder] = []
    hidden = 0
    try:
        with os.scandir(target) as entries:
            for entry in entries:
                try:
                    if not entry.is_dir(follow_symlinks=True):
                        continue
                except OSError:
                    continue
                is_hidden = _is_hidden(entry)
                if is_hidden and not show_hidden:
                    hidden += 1
                    continue
                folders.append(Folder(entry.name, str(target / entry.name), is_hidden))
    except PermissionError:
        return _with_error(base, "permission_denied")
    except FileNotFoundError:
        return _with_error(base, "not_found")
    except NotADirectoryError:
        return _with_error(base, "not_a_folder")
    except OSError:
        return _with_error(base, "unavailable")

    folders.sort(key=lambda f: (f.name.casefold(), f.name))
    return FolderListing(path=base.path, parent=base.parent, breadcrumbs=base.breadcrumbs,
                         entries=tuple(folders[:max_entries]), hidden_count=hidden,
                         truncated=len(folders) > max_entries)


def _with_error(listing: FolderListing, error: FolderError) -> FolderListing:
    return FolderListing(path=listing.path, parent=listing.parent,
                         breadcrumbs=listing.breadcrumbs, error=error)
