"""Report the state of every git repository under a folder.

Lists each repository under the root (default: the current directory) by its path from the root,
with ✔ when everything is committed and pushed, or ✘ and what needs attention:

  📝 uncommitted files            📦 stashes
  📤 commits on no remote         🔌 no remote
  📥 behind the upstream          📁 not a git repository
  👻 commits on detached HEAD     📡 fetch failed (with --fetch)
                                  💥 git failed

A folder that holds files but is in no repository is listed as not a git repository.
Ends with a count of those needing attention. Colour is used on a terminal, or with FORCE_COLOR
set, unless NO_COLOR is set.

Exit status: 0 all clean, 1 something needs attention, 2 usage error.
"""

import argparse
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

FETCH_WORKERS = 8
FETCH_TIMEOUT_SECONDS = 60

# The emoji marking each kind of problem.
UNCOMMITTED = "📝"
UNPUSHED = "📤"
BEHIND = "📥"
DETACHED = "👻"
STASHED = "📦"
NO_REMOTE = "🔌"
NOT_A_REPO = "📁"
FETCH_FAILED = "📡"
GIT_FAILED = "💥"

# ANSI escape codes for terminal styles.
RESET = "\x1b[0m"
BOLD = "\x1b[1m"
GREY = "\x1b[38;5;246m"
RED = "\x1b[31m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"


@dataclass
class Folder:
    """A repository, or a folder of files that should probably be one."""

    path: Path
    is_repo: bool
    problems: list[str] = field(default_factory=list)


def find(folder: Path) -> list[Folder]:
    """The repositories below folder, and the folders of files in no repository, in name order.

    A folder holding only folders is a group, and is searched. Repositories are assumed not to
    be nested, so the search stops at each one and never walks into node_modules and the like.
    Hidden folders and symlinks are skipped.
    """
    found = []
    for child in sorted(folder.iterdir()):
        if child.name.startswith(".") or child.is_symlink() or not child.is_dir():
            continue
        if (child / ".git").exists():
            found.append(Folder(child, is_repo=True))
        elif any(f.is_file() and f.name != ".DS_Store" for f in child.iterdir()):
            found.append(Folder(child, is_repo=False))
        else:
            found.extend(find(child))
    return found


def git(repo: Path, *args: str) -> str:
    """Run a git command in repo and return its output. Raises CalledProcessError on failure."""
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout


def count(n: int, noun: str) -> str:
    """'1 file', '2 files'."""
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def check(repo: Path) -> list[str]:
    """What in the repository needs attention."""
    problems = []

    has_remote = bool(git(repo, "remote").strip())
    if not has_remote:
        problems.append(f"{NO_REMOTE} no remote")

    uncommitted = len(git(repo, "status", "--porcelain").splitlines())
    if uncommitted:
        problems.append(f"{UNCOMMITTED} {count(uncommitted, 'uncommitted file')}")

    branches = git(
        repo, "for-each-ref", "--format=%(refname:short)\t%(upstream:track,nobracket)", "refs/heads"
    )
    for line in branches.splitlines():
        branch, _, track = line.partition("\t")
        # Count commits on no remote, rather than ahead of the upstream, so that a branch
        # without an upstream is still checked. With no remote, "no remote" already says it all.
        if has_remote:
            unpushed = int(
                git(repo, "rev-list", "--count", f"refs/heads/{branch}", "--not", "--remotes")
            )
            if unpushed:
                problems.append(f"{UNPUSHED} {unpushed} unpushed on {branch}")
        # track is like "ahead 1, behind 2", as of the last fetch.
        if behind := re.search(r"behind (\d+)", track):
            problems.append(f"{BEHIND} {behind[1]} behind on {branch}")

    on_branch = subprocess.run(
        ["git", "-C", str(repo), "symbolic-ref", "-q", "HEAD"], capture_output=True
    )
    if on_branch.returncode != 0:
        detached = int(git(repo, "rev-list", "--count", "HEAD", "--not", "--branches", "--remotes"))
        if detached:
            problems.append(f"{DETACHED} {count(detached, 'commit')} on detached HEAD")

    stashes = len(git(repo, "stash", "list").splitlines())
    if stashes:
        problems.append(f"{STASHED} {count(stashes, 'stash')}")

    return problems


def fetch(repo: Path) -> bool:
    """Fetch all of the repository's remotes. False if that failed or needed a password."""
    env = os.environ | {
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_SSH_COMMAND": os.environ.get("GIT_SSH_COMMAND", "ssh") + " -o BatchMode=yes",
    }
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "fetch", "-q", "--all"],
            capture_output=True,
            env=env,
            timeout=FETCH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="repo-list",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("root", nargs="?", default=".", help="default: the current directory")
    parser.add_argument(
        "-f",
        "--fetch",
        action="store_true",
        help="fetch every repository first, in parallel, so behind counts are current",
    )
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {args.root}")

    folders = find(root)
    if not folders:
        print(f"No repositories under {root}")
        return 0
    repos = [f for f in folders if f.is_repo]

    if args.fetch:
        with ThreadPoolExecutor(FETCH_WORKERS) as pool:
            fetched = pool.map(fetch, [r.path for r in repos])
        for repo, ok in zip(repos, fetched, strict=True):
            if not ok:
                repo.problems.append(f"{FETCH_FAILED} fetch failed")

    for folder in folders:
        if not folder.is_repo:
            folder.problems.append(f"{NOT_A_REPO} not a git repository")
        else:
            try:
                folder.problems[:0] = check(folder.path)
            except subprocess.CalledProcessError:
                folder.problems.append(f"{GIT_FAILED} git failed")

    colour = Style(enabled=wants_colour())
    width = max(len(str(f.path.relative_to(root))) for f in folders)
    for folder in folders:
        path = folder.path.relative_to(root)
        parent = "" if path.parent == Path(".") else f"{path.parent}/"
        name = colour(GREY, parent) + colour(BOLD, path.name)
        if folder.problems:
            padding = " " * (width - len(str(path)))
            problems = "  ".join(folder.problems)
            print(f"{colour(RED, '✘')} {name}{padding}  {colour(YELLOW, problems)}")
        else:
            print(f"{colour(GREEN, '✔')} {name}")

    attention = sum(1 for f in folders if f.problems)
    print()
    if not attention:
        print(colour(GREEN, f"✔ All {len(folders)} clean"))
        return 0
    print(colour(RED, f"✘ {attention} of {len(folders)} need attention"))
    return 1


def wants_colour() -> bool:
    """Colour on a terminal, or when FORCE_COLOR is set, unless NO_COLOR is set (no-color.org)."""
    if os.environ.get("NO_COLOR"):
        return False
    return bool(os.environ.get("FORCE_COLOR")) or sys.stdout.isatty()


@dataclass
class Style:
    enabled: bool

    def __call__(self, code: str, text: str) -> str:
        """text in the style given by code, or as it is when colour is off or text is empty."""
        return f"{code}{text}{RESET}" if self.enabled and text else text


if __name__ == "__main__":
    raise SystemExit(main())
