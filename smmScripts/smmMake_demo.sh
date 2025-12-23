#!/usr/bin/env bash
set -euo pipefail

# Generate the demo GIF showing order book smmDepth and trade tape snapshots.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

python -m python.scripts.make_demo "$@"


