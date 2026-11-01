#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
make
exec python3 server.py
