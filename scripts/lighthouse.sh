#!/usr/bin/env bash
# Lighthouse CI against the production build (docs/06 section 15, NFR-11).
# The gate is 4x CPU slowdown without network throttling. Simulated slow 4G is only reported.
#
# Without LIGHTHOUSE_BASE_URL it starts its own API, on a throwaway copy of the data, and
# `vite preview`, and stops both on exit. With it, it audits a running stack (compose in CI).
# LIGHTHOUSE_CHROME_FLAGS replaces the Chrome flags only. Never use LHCI_COLLECT__SETTINGS__*
# for that: those variables discard every other setting, throttling included.
# Reports: frontend/.lighthouseci/reports
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root/frontend"
base="${LIGHTHOUSE_BASE_URL:-}"
pids=()
stop() {
  if ((${#pids[@]})); then
    kill "${pids[@]}" 2>/dev/null || true
    wait "${pids[@]}" 2>/dev/null || true
  fi
}
trap stop EXIT

listening() { (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }

if [[ -z "$base" ]]; then
  api_port=8010
  web_port=4183
  for port in "$api_port" "$web_port"; do
    if listening "$port"; then
      echo "Port $port is busy; stop what uses it first." >&2
      exit 1
    fi
  done
  pnpm -s vite build
  pnpm -s size
  uv run --project "$root/backend" python "$root/scripts/e2e_api.py" --port "$api_port" &
  pids+=($!)
  API_PROXY_TARGET="http://127.0.0.1:$api_port" \
    node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port "$web_port" --strictPort &
  pids+=($!)
  for _ in $(seq 1 120); do
    if listening "$api_port" && listening "$web_port"; then break; fi
    sleep 1
  done
  base="http://127.0.0.1:$web_port"
fi

# The project-local Chromium that Playwright installed; no global Chrome needed.
CHROME_PATH="$(PLAYWRIGHT_BROWSERS_PATH=0 node -e \
  'process.stdout.write(require("@playwright/test").chromium.executablePath())')"
export CHROME_PATH

urls=(--url="$base/" --url="$base/?q=kidney" --url="$base/patients" --url="$base/quality")
flags=()
if [[ -n "${LIGHTHOUSE_CHROME_FLAGS:-}" ]]; then
  flags=("--settings.chromeFlags=$LIGHTHOUSE_CHROME_FLAGS")
fi
rm -rf .lighthouseci

mobile=--config=lighthouserc.mobile.json
mobile_report() {
  pnpm -s lhci collect "$mobile" "${flags[@]}" "${urls[@]}" &&
    pnpm -s lhci upload "$mobile" &&
    echo "Simulated slow 4G mobile, reported and not gated:" &&
    node -e 'for (const r of require("./.lighthouseci/reports/mobile/manifest.json"))
      if (r.isRepresentativeRun) console.log(" ", r.summary.performance, r.url)'
}
mobile_report || echo "The slow 4G report failed; it does not gate the build." >&2

pnpm -s lhci collect "${flags[@]}" "${urls[@]}"
pnpm -s lhci upload
pnpm -s lhci assert
