#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

apt-get update
apt-get install -y --no-install-recommends chromium fonts-liberation
rm -rf /var/lib/apt/lists/*
python -m pip install --no-cache-dir -r "$SCRIPT_DIR/requirements.txt"
