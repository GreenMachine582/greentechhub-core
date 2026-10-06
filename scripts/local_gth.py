"""Local GTH mode: run a repo against the sibling greentechhub-* working trees
instead of their pinned releases. See CONTRIBUTING.md, "Developing against
local GTH repos".

Run with the *consumer's* venv python (each repo's scripts/use-local-gth.sh
does that):

    python local_gth.py --project DIR            # link the siblings (editable)
    python local_gth.py --project DIR --status   # local or released, per dependency
    python local_gth.py --project DIR --undo     # back to the declared pins

It changes only the venv. The project's pyproject.toml / requirements.txt and
git state are never touched, so CI and production keep installing the pins.

The greentechhub-* dependencies are the ones the project declares
(pyproject.toml's dependencies and optional-dependencies, or
requirements*.txt), linked in dependency order. A dependency without a
checkout next to the project is skipped with a warning. Siblings are
installed with --no-deps, so pip doesn't pull the pinned release back in; a
new third-party dependency in a sibling needs a plain `pip install`.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

#: Dependency order: a package comes after everything it builds on.
ORDER = ["greentechhub-core", "greentechhub-fastapi", "greentechhub-ui", "greentechhub-django"]

_REQUIREMENT = re.compile(
    r"^\s*(greentechhub-[a-z0-9-]+)\s*(\[[^\]]*\])?\s*@\s*\S+", re.IGNORECASE
)


@dataclass(frozen=True)
class Requirement:
    name: str  # e.g. "greentechhub-core"
    spec: str  # the declared line, e.g. "greentechhub-core[crypto] @ git+…@v0.12.0"


def parse_requirement(line: str) -> Requirement | None:
    """The greentechhub-* direct reference on `line`, or None."""
    line = line.split(" #", 1)[0].strip()
    match = _REQUIREMENT.match(line)
    if not match:
        return None
    return Requirement(name=match.group(1).lower(), spec=line)


def declared_requirements(project: Path) -> list[Requirement]:
    """The greentechhub-* dependencies `project` declares, in dependency order."""
    lines: list[str] = []
    pyproject = project / "pyproject.toml"
    if pyproject.is_file():
        meta = tomllib.loads(pyproject.read_text(encoding="utf-8")).get("project", {})
        lines += meta.get("dependencies", [])
        for group in meta.get("optional-dependencies", {}).values():
            lines += group
    for path in sorted(project.glob("requirements*.txt")):
        lines += path.read_text(encoding="utf-8").splitlines()
    found: dict[str, Requirement] = {}
    for line in lines:
        requirement = parse_requirement(line)
        if requirement and requirement.name not in found:
            found[requirement.name] = requirement
    return ordered(found.values())


def ordered(requirements) -> list[Requirement]:
    def rank(requirement: Requirement):
        known = requirement.name in ORDER
        return (0, ORDER.index(requirement.name)) if known else (1, requirement.name)

    return sorted(requirements, key=rank)


# what the venv has

_INSPECT = """
import json, sys
from importlib import metadata
out = {}
for name in sys.argv[1:]:
    try:
        dist = metadata.distribution(name)
    except metadata.PackageNotFoundError:
        out[name] = None
        continue
    direct = dist.read_text("direct_url.json")
    out[name] = {"version": dist.version, "direct_url": json.loads(direct) if direct else None}
print(json.dumps(out))
"""


def inspect(names: list[str]) -> dict:
    """name → {"version", "direct_url"} (or None if not installed), read by a
    fresh interpreter so it sees what pip just did."""
    result = subprocess.run([sys.executable, "-c", _INSPECT, *names],
                            check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def editable_path(info: dict | None) -> Path | None:
    """Where an editable install points, or None if it isn't one."""
    direct = (info or {}).get("direct_url") or {}
    if not direct.get("dir_info", {}).get("editable"):
        return None
    return Path(url2pathname(urlparse(direct["url"]).path))


def released_revision(info: dict | None) -> str | None:
    direct = (info or {}).get("direct_url") or {}
    return direct.get("vcs_info", {}).get("requested_revision")


def same_path(a: Path, b: Path) -> bool:
    return os.path.normcase(a.resolve()) == os.path.normcase(b.resolve())


def git(path: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "?"


# commands


def pip(*args: str) -> None:
    command = [sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check"]
    subprocess.run([*command, *args], check=True)


def enable(project: Path, requirements: list[Requirement]) -> int:
    linked = []
    for requirement in requirements:
        sibling = project.parent / requirement.name
        if sibling.is_dir():
            linked.append((requirement, sibling))
        else:
            print(f"warning: {requirement.name}: no checkout at {sibling}; keeping the release")
    if not linked:
        return 0
    pip("--no-deps", *[arg for _, sibling in linked for arg in ("-e", str(sibling))])
    installed = inspect([r.name for r, _ in linked])
    failed = False
    for requirement, sibling in linked:
        path = editable_path(installed.get(requirement.name))
        if path is None or not same_path(path, sibling):
            print(f"error: {requirement.name} is not editable at {sibling} after pip",
                  file=sys.stderr)
            failed = True
        else:
            print(f"{requirement.name}: local → {sibling}")
    return 1 if failed else 0


def undo(requirements: list[Requirement]) -> int:
    pip("--force-reinstall", "--no-deps", *[r.spec for r in requirements])
    installed = inspect([r.name for r in requirements])
    failed = False
    for requirement in requirements:
        info = installed.get(requirement.name)
        if info is None or editable_path(info) is not None:
            print(f"error: {requirement.name} is still not the declared release", file=sys.stderr)
            failed = True
        else:
            print(f"{requirement.name}: released {info['version']}"
                  f" ({released_revision(info) or 'pinned'})")
    return 1 if failed else 0


def status(project: Path, requirements: list[Requirement]) -> int:
    installed = inspect([r.name for r in requirements])
    print(f"GTH local development status ({project.name})")
    for requirement in requirements:
        info = installed.get(requirement.name)
        print(f"\n{requirement.name}")
        path = editable_path(info)
        if info is None:
            print("  ✗ not installed")
        elif path is not None:
            print(f"  ✓ local editable\n  → {path}")
            print(f"  → branch: {git(path, 'rev-parse', '--abbrev-ref', 'HEAD')}")
            print(f"  → commit: {git(path, 'rev-parse', '--short', 'HEAD')}")
        else:
            print(f"  ✗ released\n  → {info['version']} ({released_revision(info) or 'pinned'})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--project", type=Path, default=Path.cwd(),
                        help="the repo whose venv is being set up (default: the current directory)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true",
                      help="show local vs released, change nothing")
    mode.add_argument("--undo", action="store_true", help="reinstall the declared releases")
    args = parser.parse_args(argv)
    project = args.project.resolve()
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    requirements = declared_requirements(project)
    if not requirements:
        print(f"{project.name} declares no greentechhub-* dependencies; nothing to do.")
        return 0
    if args.status:
        return status(project, requirements)
    if args.undo:
        return undo(requirements)
    return enable(project, requirements)


if __name__ == "__main__":
    sys.exit(main())
