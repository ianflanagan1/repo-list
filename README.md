# repo-list

Reports the state of every git repository under a folder, so nothing is left uncommitted or unpushed.

```
$ repo-list ~/projects
✘ blog          📝 3 uncommitted files  📤 2 unpushed on main
✔ dotfiles
✘ notes         📁 not a git repository
✔ work/api
✘ work/website  🔌 no remote

✘ 3 of 5 need attention
```

Each repository is listed by its path from the root, in name order, with ✔ when it is clean or ✘ and what needs attention:

- 📝 **uncommitted files**: changed, staged or untracked
- 📤 **unpushed on *branch***: commits on a local branch that are on no remote, whether or not the branch has an upstream
- 📥 **behind on *branch***: commits on the branch's upstream that it lacks, as of the last fetch
- 👻 **commits on detached HEAD**: commits reachable from no branch or remote
- 📦 **stashes**
- 🔌 **no remote**
- 📁 **not a git repository**: a folder that holds files but is in no repository, such as a project not yet initialised
- 📡 **fetch failed**: with `--fetch` only
- 💥 **git failed**: git couldn't read the repository

The last line totals them, for when the list scrolls off the screen: `✘ 3 of 5 need attention`, or `✔ All 5 clean`.

On a terminal the parent path is grey, the repository's name is bold and the problems are yellow. `NO_COLOR=1` turns colour off; `FORCE_COLOR=1` keeps it when piping.

## How it searches

It assumes repositories are not nested, so it stops descending at each one and never walks into `node_modules`, `vendor` and the like. A folder holding only folders, such as `work/`, is a group and is searched. A folder holding any file (other than `.DS_Store`) is a project, and is reported if it is not a repository. Empty folders, hidden folders and symlinks are skipped.

## Setup

After cloning, run once:

```sh
devbox run setup
```

It prints an alias to add to your shell config, such as:

```sh
alias rl='~/projects/repo-list/repo-list ~/projects'
```

Then `rl` from any directory, or `rl -f` to fetch first. `setup.sh` explains what setup does, if you're curious.

## Usage

```
repo-list [-f|--fetch] [root]
```

`root` defaults to the current directory. `-f` runs `git fetch --all` in every repository first, eight at a time, so the behind counts are current. Without it nothing touches the network.

Exit status: 0 all clean, 1 something needs attention, 2 usage error or not set up.

## Development

```sh
devbox run test   # pytest
devbox run lint   # ruff check and format
```
