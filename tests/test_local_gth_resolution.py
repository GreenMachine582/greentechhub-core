"""scripts/local_gth.py: where each package's local checkout is found, and in what order."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "local_gth.py"
CORE = "greentechhub-core"


@pytest.fixture(scope="module")
def local_gth():
    spec = importlib.util.spec_from_file_location("local_gth_resolution", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("GTH_ROOT", "GTH_CORE_PATH", "GTH_GREENTECHHUB_CORE_PATH", "GTH_FASTAPI_PATH"):
        monkeypatch.delenv(name, raising=False)


def make_dir(path: Path) -> Path:
    path.mkdir(parents=True)
    return path


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=cwd, check=True, capture_output=True,
    )


@pytest.fixture
def project(tmp_path):
    """A plain (non-git) project folder, with its sibling `greentechhub-core` beside it."""
    make_dir(tmp_path / "work" / CORE)
    return make_dir(tmp_path / "work" / "app")


def write_link(project: Path, target: Path) -> None:
    (project / ".repo-kit.local.toml").write_text(
        f'# Written by `rk wt start --link`.\n[links]\n"{CORE}" = "{target.as_posix()}"\n',
        encoding="utf-8",
    )


def test_the_sibling_is_the_default(local_gth, project):
    assert local_gth.resolve(project, CORE) == project.parent / CORE


def test_nothing_found_is_none(local_gth, tmp_path):
    assert local_gth.resolve(make_dir(tmp_path / "lonely"), CORE) is None


def test_gth_root_beats_the_sibling(local_gth, project, tmp_path, monkeypatch):
    root = make_dir(tmp_path / "root")
    make_dir(root / CORE)
    monkeypatch.setenv("GTH_ROOT", str(root))
    assert local_gth.resolve(project, CORE) == root / CORE


def test_a_gth_root_without_the_package_falls_through(local_gth, project, tmp_path, monkeypatch):
    monkeypatch.setenv("GTH_ROOT", str(make_dir(tmp_path / "empty-root")))
    assert local_gth.resolve(project, CORE) == project.parent / CORE


def test_the_package_env_var_beats_gth_root(local_gth, project, tmp_path, monkeypatch):
    root = make_dir(tmp_path / "root")
    make_dir(root / CORE)
    chosen = make_dir(tmp_path / "chosen")
    monkeypatch.setenv("GTH_ROOT", str(root))
    monkeypatch.setenv("GTH_CORE_PATH", str(chosen))
    assert local_gth.resolve(project, CORE) == chosen


def test_the_long_env_var_form_is_not_read(local_gth, project, tmp_path, monkeypatch):
    monkeypatch.setenv("GTH_GREENTECHHUB_CORE_PATH", str(make_dir(tmp_path / "long-form")))
    assert local_gth.resolve(project, CORE) == project.parent / CORE


def test_env_name_drops_the_prefix(local_gth):
    assert local_gth.env_name("greentechhub-core") == "GTH_CORE_PATH"
    assert local_gth.env_name("greentechhub-fastapi") == "GTH_FASTAPI_PATH"


def test_the_link_file_beats_the_env_var(local_gth, project, tmp_path, monkeypatch):
    linked = make_dir(tmp_path / "linked")
    monkeypatch.setenv("GTH_CORE_PATH", str(make_dir(tmp_path / "from-env")))
    write_link(project, linked)
    assert local_gth.resolve(project, CORE) == linked


def test_the_link_file_only_covers_the_packages_it_names(local_gth, project, tmp_path):
    write_link(project, make_dir(tmp_path / "linked"))
    make_dir(project.parent / "greentechhub-ui")
    assert local_gth.resolve(project, "greentechhub-ui") == project.parent / "greentechhub-ui"


def test_a_missing_explicit_path_warns_and_falls_through(local_gth, project, tmp_path, capsys):
    write_link(project, tmp_path / "gone")
    assert local_gth.resolve(project, CORE) == project.parent / CORE
    out = capsys.readouterr().out
    assert ".repo-kit.local.toml" in out
    assert "doesn't exist" in out


def test_a_relative_link_is_read_from_the_project(local_gth, project):
    (project / ".repo-kit.local.toml").write_text(
        f'[links]\n"{CORE}" = "../{CORE}"\n', encoding="utf-8"
    )
    assert local_gth.resolve(project, CORE) == project / ".." / CORE


def test_a_worktree_finds_the_siblings_of_the_main_checkout(local_gth, tmp_path):
    make_dir(tmp_path / "dev" / CORE)
    main = make_dir(tmp_path / "dev" / "app")
    git(main, "init", "-q", "-b", "main")
    git(main, "commit", "-q", "--allow-empty", "-m", "init")
    worktree = tmp_path / "elsewhere" / "app-feat-x"
    git(main, "worktree", "add", "-q", "-b", "feat/x", str(worktree))

    assert local_gth.main_checkout(worktree).resolve() == main.resolve()
    assert local_gth.main_checkout(main).resolve() == main.resolve()
    # Not next to the worktree: there is no greentechhub-core in tmp_path/elsewhere.
    assert local_gth.resolve(worktree, CORE).resolve() == (tmp_path / "dev" / CORE).resolve()


def test_enable_links_what_resolve_found(local_gth, project, tmp_path, monkeypatch, capsys):
    """`enable` goes through the resolver, not `project.parent`."""
    (project / "requirements.txt").write_text(
        f"{CORE} @ git+https://github.com/GreenMachine582/{CORE}.git@v0.12.0\n"
    )
    chosen = make_dir(tmp_path / "chosen")
    monkeypatch.setenv("GTH_CORE_PATH", str(chosen))
    calls = []
    monkeypatch.setattr(local_gth, "pip", lambda *args: calls.append(args))
    monkeypatch.setattr(
        local_gth, "inspect",
        lambda names: {n: {"direct_url": {"url": chosen.as_uri(), "dir_info": {"editable": True}}}
                       for n in names},
    )
    assert local_gth.enable(project, local_gth.declared_requirements(project)) == 0
    assert calls == [("--no-deps", "-e", str(chosen))]
    assert "local" in capsys.readouterr().out
