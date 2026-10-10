"""Fixtures shared by the tests.

Every test starts in an empty folder, `projects.root`, to be searched, with HOME pointed inside
the test's temporary directory, so no real git config is read. Bare remotes go in
`projects.remotes`, outside the searched folder.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

import repo_list


def git(*args: str | Path) -> None:
    subprocess.run(["git", *map(str, args)], check=True, capture_output=True)


class Projects:
    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "root"
        self.remotes = tmp_path / "remotes"
        self.root.mkdir()
        self.remotes.mkdir()

    def local_repo(self, name: str) -> Path:
        """A repository under the root with one commit and no remote."""
        repo = self.root / name
        git("init", "-q", repo)
        self.commit(repo, "init")
        return repo

    def pushed_repo(self, name: str) -> Path:
        """A repository under the root with one commit, pushed to its own bare origin."""
        repo = self.local_repo(name)
        origin = self.origin(repo)
        git("init", "-q", "--bare", origin)
        git("-C", repo, "remote", "add", "origin", origin)
        git("-C", repo, "push", "-qu", "origin", "main")
        return repo

    def origin(self, repo: Path) -> Path:
        return self.remotes / (repo.relative_to(self.root).as_posix().replace("/", "_") + ".git")

    def push_from_elsewhere(self, repo: Path) -> None:
        """Push a new commit to the repo's origin from another clone."""
        elsewhere = self.remotes.parent / "elsewhere"
        git("clone", "-q", self.origin(repo), elsewhere)
        self.commit(elsewhere, "ahead")
        git("-C", elsewhere, "push", "-q")

    @staticmethod
    def commit(repo: Path, message: str) -> None:
        """Add a line to the repo's file f and commit it."""
        with open(repo / "f", "a") as f:
            f.write(message + "\n")
        git("-C", repo, "add", "-A")
        git("-C", repo, "commit", "-qm", message)


@pytest.fixture(autouse=True)
def projects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Projects:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    git("config", "--global", "user.name", "test")
    git("config", "--global", "user.email", "test@example.com")
    git("config", "--global", "commit.gpgsign", "false")
    git("config", "--global", "init.defaultBranch", "main")
    projects = Projects(tmp_path)
    monkeypatch.chdir(projects.root)
    return projects


@dataclass
class Report:
    listing: list[str]
    """The per-repository lines."""
    summary: str
    """The line after them."""
    status: int


@pytest.fixture
def run(capsys: pytest.CaptureFixture[str]):
    """Run repo-list with the given arguments and return its report."""

    def run(*args: str | Path) -> Report:
        status = repo_list.main([str(a) for a in args])
        listing, _, summary = capsys.readouterr().out.rstrip("\n").partition("\n\n")
        return Report(listing.splitlines(), summary, status)

    return run
