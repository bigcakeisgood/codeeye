#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This build script targets Linux. Run it on the Linux distribution you want to build for." >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

# Use the project venv for every Python/build command.
# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install --upgrade nuitka zstandard

if ! command -v patchelf >/dev/null 2>&1; then
  echo "Warning: patchelf is not installed. Install it with your distro package manager for best standalone results." >&2
fi

python -m nuitka \
  --standalone \
  --enable-plugin=pyqt6 \
  --include-qt-plugins=platforms \
  --include-package=cv2 \
  --include-package=zxingcpp \
  --include-package=qrcode \
  --include-package=barcode \
  --output-dir=dist \
  --output-filename=CodeEye \
  main.py

echo
echo "Build finished. Try: ./dist/main.dist/CodeEye"
echo "If the output directory name differs, inspect the dist/ directory."
