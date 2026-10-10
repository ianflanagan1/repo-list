"""Behaviour of the repo-list launcher, which runs repo_list.py with the set-up Python."""

import os
import shutil
import subprocess
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent


def launch(launcher: Path, *args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([launcher, *map(str, args)], capture_output=True, text=True)


def test_the_launcher_runs_repo_list(projects):
    projects.pushed_repo("a")
    result = launch(PROJECT / "repo-list", projects.root)
    assert result.stdout == "✔ a\n\n✔ All 1 clean\n"


def test_the_launcher_works_through_a_symlink(projects, tmp_path):
    projects.pushed_repo("a")
    os.symlink(PROJECT / "repo-list", tmp_path / "rl")
    assert launch(tmp_path / "rl", projects.root).returncode == 0


def test_before_setup_the_launcher_says_how_to_set_up(projects, tmp_path):
    clone = tmp_path / "clone"
    clone.mkdir()
    for name in ("repo-list", "repo_list.py"):
        shutil.copy2(PROJECT / name, clone)
    result = launch(clone / "repo-list", projects.root)
    assert result.returncode == 2
    assert "devbox run setup" in result.stderr
