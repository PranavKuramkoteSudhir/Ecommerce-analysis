"""Public foundation tests: must also pass without any private planning files."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "check_foundation", ROOT / "scripts" / "check_foundation.py"
)
assert SPEC is not None and SPEC.loader is not None
CHECKS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKS)


class FoundationTests(unittest.TestCase):
    def test_private_and_generated_paths_are_ignored(self):
        paths = [
            ".project/backlog.yaml",
            ".project/stages/S01-local-platform.md",
            "AGENTS.md",
            "services/example/AGENTS.md",
            ".env",
            ".env.local",
            "infra/private.key",
            ".venv/bin/python",
            "reports/results.json",
        ]
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--stdin"],
            input="\n".join(paths) + "\n",
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(result.stdout.splitlines()), set(paths))

    def test_public_files_are_not_ignored(self):
        paths = [
            "README.md",
            "pyproject.toml",
            ".env.example",
            "tests/unit/test_foundation.py",
            ".github/workflows/ci.yml",
        ]
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--stdin"],
            input="\n".join(paths) + "\n",
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_path_policy_rejects_private_material(self):
        for name in [
            ".project/proposal.md",
            "services/accounts/AGENTS.md",
            ".env.production",
            "infra/tls.key",
            "docs/project-proposal.md",
        ]:
            with self.subTest(name=name):
                self.assertTrue(CHECKS.forbidden_path(name))

    def test_path_policy_allows_implementation_artifacts(self):
        for name in ["README.md", ".env.example", "contracts/event.json", "tests/x.py"]:
            with self.subTest(name=name):
                self.assertFalse(CHECKS.forbidden_path(name))

    def test_python_runtime_is_explicit(self):
        config = tomllib.loads((ROOT / "pyproject.toml").read_text())
        self.assertEqual(config["project"]["requires-python"], ">=3.12,<3.13")
        self.assertEqual(config["project"]["dependencies"], [])

    def test_readme_does_not_link_private_planning(self):
        readme = (ROOT / "README.md").read_text()
        for target in ["](.project/", "](docs/project-proposal.md)", "](AGENTS.md)"]:
            self.assertNotIn(target, readme)


if __name__ == "__main__":
    unittest.main()
