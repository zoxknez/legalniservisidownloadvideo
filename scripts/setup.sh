#!/usr/bin/env bash
# One-shot dev setup (Linux / macOS)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Python venv"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
pip install -e ".[dev]"

echo "==> Frontend"
cd frontend
if [[ ! -d node_modules ]]; then
  npm ci
else
  npm install
fi
npm run build
cd ..

echo ""
echo "Gotovo. Pokrenite: python run.py"
echo "Razvoj UI: cd frontend && npm run dev  (backend na :8000)"
