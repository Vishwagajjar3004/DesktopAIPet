#!/usr/bin/env bash
# Build script for Linux: creates dist/Asha/Asha
# Run from the project root: bash packaging/build_linux.sh
set -euo pipefail

cd "$(dirname "$0")/.."

python3 -m venv .venv_build
source .venv_build/bin/activate

pip install -r requirements.txt
pip install pyinstaller

pyinstaller packaging/asha.spec --noconfirm --clean

echo
echo "Build complete. See dist/Asha/Asha"
