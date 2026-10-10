#!/bin/sh
# Set up repo-list after cloning it. Run with `devbox run setup`.
#
# Why this is needed: the launcher, ./repo-list, runs repo_list.py with the Python in .venv, so
# it works from any directory without starting devbox (which is slower, and prints its own error
# line whenever repo-list reports a problem). .venv doesn't come with the clone: devbox's Python
# plugin creates it, linked to the Python that devbox.json pins, the first time devbox starts
# here. `devbox run setup` is that first start; this script then checks it worked.

set -eu

here=$(cd "$(dirname "$0")" && pwd -P)
if [ ! -x "$here/.venv/bin/python" ]; then
    echo "✘ $here/.venv was not created. Run this with: devbox run setup" >&2
    exit 1
fi

echo "✔ repo-list is set up. To run it from anywhere, add an alias to your shell config, e.g.:"
echo
echo "alias rl='$here/repo-list $(dirname "$here")'"
