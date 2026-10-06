"""scripts/local_gth.py (local GTH mode): which greentechhub-* dependencies a
project declares, in what order, and how an install is described."""

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "local_gth.py"


@pytest.fixture(scope="module")
def local_gth():
    spec = importlib.util.spec_from_file_location("local_gth", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CORE = "greentechhub-core[sqlalchemy] @ git+https://github.com/GreenMachine582/greentechhub-core.git@v0.12.0"
FASTAPI = "greentechhub-fastapi @ git+https://github.com/GreenMachine582/greentechhub-fastapi.git@v0.14.0"
UI = "greentechhub-ui @ git+https://github.com/GreenMachine582/greentechhub-ui.git@v0.15.0"


def test_parse_requirement_keeps_the_declared_line(local_gth):
    requirement = local_gth.parse_requirement(f"  {CORE}  # pinned")
    assert requirement.name == "greentechhub-core"
    assert requirement.spec == CORE


def test_parse_requirement_ignores_everything_else(local_gth):
    assert local_gth.parse_requirement("fastapi>=0.110") is None
    assert local_gth.parse_requirement("greentechhub-core>=0.11") is None  # not a direct reference
    assert local_gth.parse_requirement("# greentechhub-core @ git+x") is None


def test_pyproject_dependencies_and_extras_in_dependency_order(local_gth, tmp_path):
    (tmp_path / "pyproject.toml").write_text(f"""
[project]
name = "consumer"
dependencies = ["fastapi", "{UI}"]
[project.optional-dependencies]
dev = ["pytest", "{FASTAPI}", "{CORE}"]
""")
    names = [r.name for r in local_gth.declared_requirements(tmp_path)]
    assert names == ["greentechhub-core", "greentechhub-fastapi", "greentechhub-ui"]


def test_requirements_txt(local_gth, tmp_path):
    (tmp_path / "requirements.txt").write_text(f"alembic~=1.20.0\n{FASTAPI}\n{CORE}\n")
    requirements = local_gth.declared_requirements(tmp_path)
    assert [r.spec for r in requirements] == [CORE, FASTAPI]


def test_unknown_gth_packages_come_last(local_gth):
    Requirement = local_gth.Requirement
    names = [r.name for r in local_gth.ordered([
        Requirement("greentechhub-zeta", "z"), Requirement("greentechhub-ui", "u"),
        Requirement("greentechhub-core", "c"),
    ])]
    assert names == ["greentechhub-core", "greentechhub-ui", "greentechhub-zeta"]


def test_no_gth_dependencies_is_nothing_to_do(local_gth, tmp_path, capsys):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\ndependencies = ["fastapi"]\n')
    assert local_gth.main(["--project", str(tmp_path), "--status"]) == 0
    assert "nothing to do" in capsys.readouterr().out


def test_editable_path_and_released_revision(local_gth, tmp_path):
    editable = {"version": "0.12.0",
                "direct_url": {"url": tmp_path.as_uri(), "dir_info": {"editable": True}}}
    released = {"version": "0.12.0", "direct_url": {
        "url": "https://github.com/GreenMachine582/greentechhub-core.git",
        "vcs_info": {"vcs": "git", "requested_revision": "v0.12.0", "commit_id": "abc"}}}
    assert local_gth.same_path(local_gth.editable_path(editable), tmp_path)
    assert local_gth.editable_path(released) is None
    assert local_gth.editable_path(None) is None
    assert local_gth.released_revision(released) == "v0.12.0"
