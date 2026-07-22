#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 <appimage-path> [port]" >&2
  exit 2
fi

appimage_path="$(readlink -f "$1")"
port="${2:-8765}"
smoke_root="$(mktemp -d "${TMPDIR:-/tmp}/prism-appimage-smoke.XXXXXX")"
log_path="$smoke_root/launcher.log"
resources_path="$smoke_root/resources.json"
tasks_path="$smoke_root/tasks.json"

if [[ ! -x "$appimage_path" ]]; then
  echo "AppImage is not executable: $appimage_path" >&2
  exit 1
fi

"$appimage_path" \
  --appimage-extract-and-run \
  --no-browser \
  --host 127.0.0.1 \
  --port "$port" \
  >"$log_path" 2>&1 &
app_pid=$!

finish() {
  if kill -0 "$app_pid" 2>/dev/null; then
    kill "$app_pid" 2>/dev/null || true
  fi
  wait "$app_pid" 2>/dev/null || true
}
trap finish EXIT

for _attempt in $(seq 1 60); do
  if curl --fail --silent --show-error \
    "http://127.0.0.1:${port}/api/resources" \
    --output "$resources_path" && \
    curl --fail --silent --show-error \
      "http://127.0.0.1:${port}/api/tasks" \
      --output "$tasks_path"; then
    python - "$resources_path" "$tasks_path" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    resources = json.load(handle)
with open(sys.argv[2], encoding="utf-8") as handle:
    tasks = json.load(handle)

if not resources.get("judge_system_prompt", {}).get("exists"):
    raise SystemExit("bundled judge system prompt was not resolved")
for resource_name in ("prompts", "rubrics"):
    layers = resources.get(resource_name, {}).get("layers", [])
    if not any(layer.get("exists") for layer in layers):
        raise SystemExit(f"no existing {resource_name} layer was resolved")
if not tasks:
    raise SystemExit("no bundled tasks were returned")
PY
    echo "AppImage smoke test passed: bundled resources and tasks are available"
    exit 0
  fi

  if ! kill -0 "$app_pid" 2>/dev/null; then
    echo "AppImage exited before becoming ready." >&2
    sed -n '1,240p' "$log_path" >&2
    exit 1
  fi
  sleep 0.25
done

echo "Timed out waiting for AppImage startup." >&2
sed -n '1,240p' "$log_path" >&2
exit 1
