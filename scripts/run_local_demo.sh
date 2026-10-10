#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_python="$project_root/.venv/bin/python"

if [[ ! -x "$backend_python" ]]; then
  echo "Missing .venv. Create it with Python 3.11 and run: pip install -e ." >&2
  exit 1
fi

if [[ ! -d "$project_root/frontend/node_modules" ]]; then
  echo "Missing frontend dependencies. Run: cd frontend && npx -y pnpm@9 install" >&2
  exit 1
fi

cleanup() {
  if [[ -n "${backend_pid:-}" ]]; then kill "$backend_pid" 2>/dev/null || true; fi
  if [[ -n "${frontend_pid:-}" ]]; then kill "$frontend_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

cd "$project_root"
"$backend_python" scripts/run_service.py &
backend_pid=$!

cd "$project_root/frontend"
npx -y pnpm@9 dev &
frontend_pid=$!

echo "Stress Monitor is starting at http://localhost:5173"
echo "Press Ctrl+C to stop both services."
wait "$backend_pid" "$frontend_pid"
