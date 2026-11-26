#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$SCRIPT_DIR/../medtech-reference-architecture"
mode=
grid=0
secure=0
launch_args=()
for arg in "$@"; do
  case "$arg" in
    -h|--help)
      echo "Usage (internal): $0 {--setup-only|--check-launch|--launch-only} [--secure] [--vscode|--web] [DEVICE]"
      exit 0
      ;;
    --setup-only) mode=setup ;;
    --launch-only) mode=launch ;;
    --check-launch) mode=check ;;
    --secure) secure=1; launch_args+=(--security) ;;
    --vscode) grid=1 ;;
    --web) grid=0 ;;
    Orchestrator|PatientSensor|ArmController|Arm|PatientMonitor) launch_args+=("$arg") ;;
    *) echo "error: unknown runner argument $arg" >&2; exit 2 ;;
  esac
done
if [[ -z "$mode" ]]; then
  echo "error: specify --setup-only, --check-launch or --launch-only; use medtech.sh for the public command" >&2
  exit 2
fi

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
cloud_mode="${MEDTECH_CLOUD:-0}"

if [[ "$cloud_mode" != 1 ]]; then
  venv_dir="${MEDTECH_VENV:-$REPO_DIR/.venv}"
  if [[ "$mode" == setup && ! -d "$venv_dir" ]]; then
    echo "Creating virtual environment..."
    python3 -m venv "$venv_dir"
  fi
  if [[ ! -f "$venv_dir/bin/activate" ]]; then
    echo "error: virtual environment missing; run ./scripts/medtech.sh build first." >&2
    exit 1
  fi
  # shellcheck disable=SC1091
  source "$venv_dir/bin/activate"
fi

if [[ "$mode" == check ]]; then
  exec python3 "$SCRIPT_DIR/check_module_build.py" "$secure"
fi

if [[ "$mode" == setup ]]; then
  if [[ "$cloud_mode" == 1 ]]; then
    python3 -c 'import rti.connextdds, rti.idl' || {
      echo "error: shared Playground Python cannot import the Connext bindings." >&2
      exit 1
    }
  else
    echo "Installing Python dependencies..."
    python3 -m pip install -q -r requirements.txt
    python3 -m pip install -q --no-index rti.connext.activated==7.7.0 -f "$NDDSHOME/resource/python_api"
  fi

  echo "Building Module 01 (C++ targets + Python type support)..."
  if [[ "$cloud_mode" == 1 ]]; then
    if [[ ! -f /opt/medtech-deps/connext-cmake-utils/cmake/Modules/FindRTIConnextDDS.cmake ]]; then
      echo "error: offline Connext CMake utilities are missing; rebuild the Playground image." >&2
      exit 1
    fi
    python3 build.py -DFETCHCONTENT_SOURCE_DIR_RTICONNEXTDDS-CMAKE-UTILS=/opt/medtech-deps/connext-cmake-utils -- --target module-01
  else
    python3 build.py -- --target module-01
  fi
  if [[ "$secure" == 1 ]]; then
    python3 system_arch/security/setup_security.py
  fi
fi

if [[ "$mode" == setup ]]; then
  exit 0
fi
echo "Launching Digital Operating Room..."
if [[ "$grid" == 1 ]]; then
  exec python3 "$SCRIPT_DIR/medtech_grid.py" ${launch_args[@]+"${launch_args[@]}"}
fi
exec python3 launch.py 01-operating-room ${launch_args[@]+"${launch_args[@]}"}
