#!/usr/bin/env bash

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
venv_dir="$repo_root/.venv-shell"

if [[ ! -x "$venv_dir/bin/python" ]]; then
  python3 -m venv "$venv_dir"
fi

"$venv_dir/bin/python" -m pip \
  --disable-pip-version-check \
  install -r "$repo_root/requirements-shell.txt"

"$venv_dir/bin/python" - <<'PY'
from importlib.metadata import version

print(f"p4runtime-shell {version('p4runtime-shell')}")
print(f"p4runtime {version('p4runtime')}")
PY
