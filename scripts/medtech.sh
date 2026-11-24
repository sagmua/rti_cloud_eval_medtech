#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_DIR="$ROOT_DIR/medtech-reference-architecture"
usage() {
  cat <<'EOF'
Usage: ./scripts/medtech.sh {build|start|stop|restart} [OPTIONS]

  build     Prepare dependencies and build Digital Operating Room (Module 01).
  start     Build if needed, start in the background, and check readiness.
  stop      Stop this checkout's demo and close its hosted device tabs.
  restart   Stop, then build and start again.

Options for build, start and restart:
  --secure   Prepare and use the upstream DDS Security demo configuration.
  --cloud    Use the pre-provisioned Cloud Evaluation SDK, Python, and IDE.
  --vscode   Open four device panels in desktop VS Code (default locally).
  --web      Open local browser tabs instead of the VS Code grid.
  --help     Show this help without changing the workspace.

Cloud mode is the default when MEDTECH_CLOUD=1. Use stop, not Ctrl+C, after
start has returned. Build does not start the demo or install the extension.
EOF
}

action="${1:---help}"
case "$action" in
  -h|--help) usage; exit 0 ;;
  build|start|stop|restart) shift ;;
  *) echo "error: unknown command $action" >&2; usage >&2; exit 2 ;;
esac
cloud_mode="${MEDTECH_CLOUD:-0}"
display=--vscode
secure_args=()
mode_seen=
for arg in "$@"; do
  case "$arg" in
    -h|--help) usage; exit 0 ;;
    --cloud|--vscode|--web)
      if [[ -n "$mode_seen" || "$action" == stop ]]; then
        echo "error: specify at most one launch mode, and none for stop" >&2
        exit 2
      fi
      mode_seen="$arg"
      ;;
    --secure)
      if [[ "$action" == stop ]]; then
        echo "error: stop does not take --secure" >&2
        exit 2
      fi
      ;;
  esac
  case "$arg" in
    --secure) secure_args=(--secure) ;;
    --web|--vscode) display="$arg"; cloud_mode=0 ;;
    --cloud) display=--vscode; cloud_mode=1 ;;
    *) echo "error: unknown option $arg" >&2; exit 2 ;;
  esac
done
export MEDTECH_CLOUD="$cloud_mode"

case "$action" in
  stop) exec "$SCRIPT_DIR/stop.sh" ;;
  restart) "$SCRIPT_DIR/stop.sh" ;;
esac

if [[ "$action" != build ]]; then
python3 - <<'PY'
import socket

busy = []
ports = [("Orchestrator", 8090), ("Arm Controller", 8091),
     ("Arm", 8092), ("Patient Monitor", 8093)]
for name, port in ports:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            busy.append(f"{name} ({port})")
    except OSError:
        pass

if busy:
    raise SystemExit("error: demo ports already in use: " + ", ".join(busy)
                     + ". Stop the existing demo before launching another one.")
PY
fi

expected_commit=$(git -C "$ROOT_DIR" rev-parse :medtech-reference-architecture)
if [[ -e "$REPO_DIR/.git" ]]; then
  current_commit=$(git -C "$REPO_DIR" rev-parse HEAD)
  if [[ "$current_commit" != "$expected_commit" ]] &&
     { ! git -C "$REPO_DIR" diff --quiet || ! git -C "$REPO_DIR" diff --cached --quiet; }; then
    echo "error: nested repo has local changes; cannot switch to pinned commit $expected_commit" >&2
    exit 1
  fi
fi
if [[ ! -e "$REPO_DIR/.git" ]]; then
  git -C "$ROOT_DIR" submodule update --init --recursive -- medtech-reference-architecture
fi
if [[ "$(git -C "$REPO_DIR" rev-parse HEAD)" != "$expected_commit" ]]; then
  echo "error: MedTech does not match the recorded source pin; align the submodule explicitly without discarding local work." >&2
  exit 1
fi
if [[ ! -f "$REPO_DIR/launch.py" ]]; then
  echo "error: the existing source checkout is incomplete; restore it explicitly without discarding local work." >&2
  exit 1
fi

if [[ "$action" == build ]]; then
  exec "$SCRIPT_DIR/run_module.sh" --setup-only ${secure_args[@]+"${secure_args[@]}"}
fi

if [[ "$cloud_mode" == 1 ]]; then
  : "${MEDTECH_CLOUD_URL:?Set MEDTECH_CLOUD_URL to the externally accessible IDE base URL}"
  extension_version=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$ROOT_DIR/vscode-extension/package.json")
  extension_dir="${MEDTECH_CODE_SERVER_EXTENSIONS:-/config/extensions}/rti.medtech-web-tabs-$extension_version"
  if [[ ! -f "$extension_dir/extension.js" ]]; then
    echo "error: MedTech extension was not provisioned before IDE startup; recreate the pilot workspace with the matching image/source." >&2
    exit 1
  fi
  (cd "$SCRIPT_DIR" && python3 - <<'PY'
import json
import os
import time
from medtech_grid import _tab_state_dir

deadline = time.monotonic() + 15
while time.monotonic() < deadline:
    try:
        ready = json.loads((_tab_state_dir() / "ready").read_text())
        os.kill(int(ready["pid"]), 0)
        break
    except (FileNotFoundError, ProcessLookupError):
        time.sleep(0.2)
else:
    raise SystemExit("error: MedTech extension did not activate in this workspace; reload the IDE once or check its extension logs.")
PY
  )
elif [[ "$display" == --vscode ]]; then
  if command -v code >/dev/null 2>&1; then
    code_cli=$(command -v code)
  elif [[ -x "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" ]]; then
    code_cli="/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
  else
    echo "error: VS Code CLI not found; install it or run with --web." >&2
    exit 1
  fi
  if ! command -v npm >/dev/null 2>&1; then
    echo "error: Node.js/npm is required to package the device-grid extension." >&2
    exit 1
  fi
  (cd "$ROOT_DIR/vscode-extension" && npm ci --ignore-scripts --no-audit --no-fund && npm run package &&
    "$code_cli" --install-extension "$(pwd)/medtech-web-tabs-$(node -p 'require("./package.json").version').vsix" --force)
  "$code_cli" "$ROOT_DIR"
fi

"$SCRIPT_DIR/run_module.sh" --setup-only ${secure_args[@]+"${secure_args[@]}"}

if [[ "$display" == --vscode ]]; then
  echo "Opening four device apps in a 2x2 VS Code grid (no tutorial panel)."
fi
if [[ "$cloud_mode" == 1 ]]; then
  cloud_url="$MEDTECH_CLOUD_URL"
  echo "Orchestrator: ${cloud_url%/}/proxy/8090/"
  echo "Arm Controller: ${cloud_url%/}/proxy/8091/"
  echo "Arm: ${cloud_url%/}/proxy/8092/"
  echo "Patient Monitor: ${cloud_url%/}/proxy/8093/"
fi

echo "Starting Digital Operating Room demo in the background..."
DEMO_LOG=$(mktemp "${TMPDIR:-/tmp}/medtech-digital-or.XXXXXX")
nohup "$SCRIPT_DIR/run_module.sh" --launch-only "$display" ${secure_args[@]+"${secure_args[@]}"} >"$DEMO_LOG" 2>&1 </dev/null &
DEMO_PID=$!
disown "$DEMO_PID"

echo "Demo supervisor PID: $DEMO_PID"
echo "Demo log: $DEMO_LOG"
if ! python3 - "$DEMO_PID" <<'PY'
import json
import os
import sys
import time
import urllib.error
import urllib.request

deadline = time.monotonic() + 30
while time.monotonic() < deadline:
    try:
        os.kill(int(sys.argv[1]), 0)
        for port in range(8090, 8094):
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state", timeout=1) as response:
                json.load(response)
        break
    except ProcessLookupError:
        raise SystemExit("error: demo supervisor exited during startup")
    except (OSError, urllib.error.URLError):
        time.sleep(0.2)
else:
    raise SystemExit("error: demo HTTP applications did not become ready within 30 seconds")
PY
then
  cat "$DEMO_LOG" >&2
  "$SCRIPT_DIR/stop.sh"
  exit 1
fi
echo "Four device HTTP applications are ready."
echo "Stop: $SCRIPT_DIR/medtech.sh stop"
printf 'Restart: %q restart' "$SCRIPT_DIR/medtech.sh"
if [[ -n "$mode_seen" ]]; then printf ' %s' "$mode_seen"; fi
if [[ "${secure_args[0]:-}" == --secure ]]; then printf ' --secure'; fi
printf '\n'
