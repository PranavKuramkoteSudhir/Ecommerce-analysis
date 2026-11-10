"""Dependency-free foundation checks, runnable from any working directory."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def forbidden_path(name: str) -> bool:
    """Check repository paths; not a substitute for content secret scanning."""
    path = Path(name)
    return (
        path.parts[0] in {".project", ".pi", ".claude"}
        or path.name in {"AGENTS.md", "AGENTS.override.md"}
        or (path.name.startswith(".env") and path.name != ".env.example")
        or path.suffix in {".pem", ".key"}
        or name in {"docs/project-proposal.md", "docs/functional-requirements.md"}
    )


def main() -> int:
    if sys.version_info[:2] != (3, 12):
        print("ERROR: use Python 3.12 (python3.12 or make PYTHON=...).", file=sys.stderr)
        return 1

    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "-z"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"ERROR: cannot inspect Git index: {error}", file=sys.stderr)
        return 1

    tracked = result.stdout.decode().split("\0")
    forbidden = [name for name in tracked if name and forbidden_path(name)]
    if forbidden:
        print(f"ERROR: forbidden tracked paths: {forbidden}", file=sys.stderr)
        return 1

    sources = sorted((ROOT / "scripts").rglob("*.py")) + sorted(
        (ROOT / "tests").rglob("*.py")
    )
    for source in sources:
        ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    print(f"Syntax checked {len(sources)} Python files.", flush=True)

    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests" / "unit"))
    if suite.countTestCases() == 0:
        print("ERROR: no tests discovered.", file=sys.stderr)
        return 1
    outcome = unittest.TextTestRunner(verbosity=2).run(suite)
    if not outcome.wasSuccessful():
        return 1
    print("Offline foundation/plan checks passed; runtime/integration probes NOT RUN.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
