#!/usr/bin/env bash
# Sets up, builds, and launches the Digital Operating Room demo (Module 01) from the
# medtech-reference-architecture repo, for local demos ahead of any cloud eval integration.
#
# Usage: ./run_digital_or.sh [--secure] [--vscode|--web] [--setup-only|--launch-only]
#
# Requires: RTI Connext Professional 7.7 installed and licensed locally.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$SCRIPT_DIR/../medtech-reference-architecture"
mode=all
grid=0
launch_args=()
for arg in "$@"; do
  case "$arg" in
    --setup-only) mode=setup ;;
    --launch-only) mode=launch ;;
    --secure) launch_args+=(--security) ;;
    --vscode) grid=1 ;;
    --web) grid=0 ;;
    *) launch_args+=("$arg") ;;
  esac
done

if [[ ! -f "$REPO_DIR/launch.py" ]]; then
  echo "error: $REPO_DIR is missing. Initialize the medtech-reference-architecture submodule first." >&2
  exit 1
fi

if [[ -z "${NDDSHOME:-}" ]]; then
  echo "NDDSHOME is not set. Trying to auto-detect a local Connext 7.7 install..."
  CANDIDATE=$(ls -d /Applications/rti_connext_dds-7.7.0 2>/dev/null | head -1 || true)
  if [[ -z "$CANDIDATE" ]]; then
    echo "error: could not find a Connext install. Set NDDSHOME and source rtisetenv_<arch> first." >&2
    exit 1
  fi
  SETENV=$(ls "$CANDIDATE"/resource/scripts/rtisetenv_*.bash 2>/dev/null | head -1 || true)
  if [[ -z "$SETENV" ]]; then
    echo "error: could not find an rtisetenv_<arch> script under $CANDIDATE/resource/scripts." >&2
    exit 1
  fi
  echo "Sourcing $SETENV"
  set +u
  # shellcheck disable=SC1090
  source "$SETENV"
  set -u
fi

cd "$REPO_DIR"
venv_dir="${MEDTECH_VENV:-$REPO_DIR/.venv}"

if [[ "$mode" != launch ]]; then
  if [[ ! -d "$venv_dir" ]]; then
    echo "Creating virtual environment..."
    python3 -m venv "$venv_dir"
  fi
fi
if [[ ! -f "$venv_dir/bin/activate" ]]; then
  echo "error: virtual environment missing; run setup first." >&2
  exit 1
fi
# shellcheck disable=SC1091
source "$venv_dir/bin/activate"

if [[ "$mode" != launch ]]; then
  echo "Installing Python dependencies..."
  if [[ "${MEDTECH_CLOUD:-0}" == 1 ]]; then
    python3 -c 'import rti.connextdds, argcomplete' || {
      echo "error: cloud Python dependencies missing; rebuild the cloud image." >&2
      exit 1
    }
  else
    python3 -m pip install -q -r requirements.txt
    python3 -m pip install -q --no-index rti.connext.activated==7.7.0 -f "$NDDSHOME/resource/python_api"
  fi

  echo "Building Module 01 (C++ targets + Python type support)..."
  if [[ "${MEDTECH_CLOUD:-0}" == 1 ]]; then
    if [[ ! -f /opt/medtech-deps/connext-cmake-utils/cmake/Modules/FindRTIConnextDDS.cmake ]]; then
      echo "error: offline Connext CMake utilities are missing; rebuild the Playground image." >&2
      exit 1
    fi
    python3 build.py -DFETCHCONTENT_SOURCE_DIR_RTICONNEXTDDS-CMAKE-UTILS=/opt/medtech-deps/connext-cmake-utils -- --target module-01
  else
    python3 build.py -- --target module-01
  fi
fi

if [[ "$mode" == setup ]]; then
  exit 0
fi
echo "Launching Digital Operating Room..."
if [[ "$grid" == 1 ]]; then
  exec python3 "$SCRIPT_DIR/medtech_grid.py" "${launch_args[@]}"
fi
exec python3 launch.py 01-operating-room "${launch_args[@]}"
