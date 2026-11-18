# MedTech Cloud Evaluation Helper

This repository supports running the
[MedTech Reference Architecture](https://github.com/rticommunity/rticonnextdds-medtech-reference-architecture)
in Cloud Evaluation. It supplies the Digital Operating Room tutorial, lifecycle
helpers, the device-grid extension, and a pinned source submodule. Applications
and their build system remain in the reference architecture. The submodule tracks
`feature/CLOUD-701`, pinned at `1c3de45f3b21f1964b6472f45c56128d71692be9`;
normal initialization uses that commit, not a moving branch tip.

The helper is MedTech-specific, not a shared repository or framework for other
industry examples. Its original layout is retained:

```text
tutorial/                        # Tutorial and launch/stop/restart helpers
vscode-extension/                # Helper-owned VS Code/code-server device grid
medtech-reference-architecture/  # Pinned source submodule
docker/                          # Dependency lock and historical standalone recipe
```

Clone and launch locally:

```bash
git clone git@github.com:sagmua/rti_cloud_eval_medtech.git
cd rti_cloud_eval_medtech
git submodule update --init --recursive -- medtech-reference-architecture
./tutorial/launch_all.sh --vscode
```

See the [tutorial guide](tutorial/README.md) for cloud requirements.

## Cloud Image And Recovery

Hosted packaging belongs to RTI Cloud's Playground image, not this wrapper.
The [historical standalone image runbook](docker/README_cloud_eval_image.md)
records the earlier image/archive identities and backup/restore procedures;
its original bootstrap commands are not the hosted recipe.
The hash-locked Python requirements remain a versioned image-build input.
Licensed archives and volume
backups must be kept in authorized external storage; they are not included in Git.
The tutorial is a Markdown file, and the four device UIs run in a 2x2 editor grid
using the bundled device-only extension, without a tutorial panel, desktop window,
or noVNC display. Module 01 no longer needs GTK,
Qt, NumPy or pyqtgraph, even when building from source. The deployed web-only image
is 7.07 GB by Docker's storage metric; only 20.5 MB of filesystem layers are added
over the original Playground base. Historical desktop measurements and future
prebuilt packaging proposals are distinguished below.

## Dependencies

There are two different dependency sets: **building from source** and **running prebuilt applications**. The current local launcher does both. A Cloud Eval runtime image does not need to contain the compiler, CMake, development headers, or the complete Connext SDK if compatible applications and generated Python types are supplied ahead of time. It still needs the native and Python runtime libraries below.

### Build And Setup Dependencies

These belong on a developer machine or in a CI/builder image, not necessarily in the user workspace:

- Git (this public GitHub wrapper and its public MedTech submodule), Bash, and network access to PyPI for local setup. Hosted setup uses preinstalled dependencies.
- Licensed RTI Connext DDS Professional 7.7.0, including its C++ libraries, build tools, and the `rti.connext.activated` Python wheel under `$NDDSHOME/resource/python_api`. Set `NDDSHOME` and source the matching `rtisetenv_<arch>` script; the launcher auto-detects `/Applications/rti_connext_dds-7.7.0` on macOS. The script cannot download or license Connext.
- Python 3.10+ with `pip` and `venv`; CMake 3.17+; and a C++17 compiler. GTK development libraries and `pkg-config` are not needed by Module 01.

On Ubuntu/Debian, install the system build packages with `sudo apt install build-essential cmake python3-venv`; install Python and Git separately if absent. On macOS, install the Xcode command-line tools and use `brew install cmake python3 git`.

### Runtime Dependencies

These remain necessary with the current application code, even if the C++ applications are precompiled:

- Python 3.10+ and the installed Python packages listed below, including the Connext 7.7.0 Python API. `pip` and `venv` are provisioning tools, not application requirements once the environment is prepared.
- The Connext C++ shared libraries used by the binaries, compatible OS/C++ runtime libraries, and the required runtime licensing configuration. Precompilation does not remove licensing requirements; a runtime-only Connext layout and redistribution rights must be validated with RTI.
- No GTK/Qt/display stack is needed for Module 01. Its C++ binaries no longer link GTK, and its Python backends no longer import desktop libraries.
- VS Code/code-server with the bundled device-grid extension, and a Markdown viewer for the tutorial. Cloud provisioning registers the extension before IDE startup; desktop `--vscode` mode needs Node.js/npx and the `code` CLI for packaging/installation. `--web` opens local browser tabs without the extension. Native device windows are no longer supported. Hosted template provisioning still requires platform validation.

The local launcher creates a virtual environment and installs the source's Python
requirements, including NAT-tool dependencies retained for other modules. It installs
`rti.connext.activated` from the local Connext installation separately. Cloud mode
checks the preinstalled environment instead and runs only Module 01. The helper
builds the `module-01` target, which now includes generated Python type support.
The source remains independently usable with ordinary browser tabs and contains
no custom VS Code extension.

The helper's [grid adapter](tutorial/medtech_grid.py) reuses the source launcher's
command/environment resolution. Only IDE-specific process ownership, tab IPC, and
recovery supervision live here; no DDS application or build implementation is
duplicated. Run helper regression tests with `python3 -m pytest tests`, and extension
tests with `npm test --prefix vscode-extension`.

Both browser and IDE-grid sessions keep healthy applications running after a
device crash. The supervisor reports the failed process once; it does not stop
the other devices. Grid recovery remains available through Orchestrator.

### Historical Desktop Dependency Sizes

The following are historical **installed disk footprints**, not RAM use or compressed download sizes. Measurements were taken with `du -sh` on the original desktop macOS arm64 installation on 2026-09-30 (Python 3.14); they are reference points, **not Linux Cloud Eval image measurements**. The GTK/Qt/NumPy/display costs no longer apply to web-only Module 01. MiB/GiB values are rounded. Rows explicitly marked as budgets are rough Linux planning allowances, not measured package sizes. Versions, architecture, shared dependencies, and existing base-image contents change the incremental cost.

| Dependency | Build/setup | Prebuilt runtime | Installed size reference |
| --- | --- | --- | --- |
| Git | Clone and CMake FetchContent | Needed by the source pin check in `launch_all.sh` | 20-60 MiB budget with dependencies; zero added if already present |
| Bash | Setup scripts | Needed by the shell launch scripts | 1-5 MiB budget; zero added if already present |
| C++17 compiler/toolchain | Required | Not needed; retain OS/C++ runtime libraries | 1.3 GiB measured for macOS command-line tools; Linux builder budget 250-600 MiB |
| CMake >=3.17 | Required | Not needed | 74 MiB measured |
| `pkg-config` | Historical GTK build discovery | Not needed | 0.6 MiB measured (`pkgconf`) |
| Connext Professional 7.7.0 SDK | Required, including code generator | Full SDK not intrinsically needed | 2.7 GiB measured for the complete local installation |
| Connext C++ libraries | Link libraries | Required shared-library subset | 690 MiB measured for the entire local architecture library directory, **not** a minimal runtime; subset size TBD after dependency audit |
| Connext Python API | Install for Python apps | Required | 34 MiB measured installed `rti` package; bundled wheel directory is 47 MiB and need not ship in runtime |
| Python >=3.10 | Build scripts and environment setup | Required | 88 MiB measured Homebrew Python package, excluding external shared libraries |
| GTK/gtkmm | Historical desktop build | Not needed by Module 01 | 11 MiB measured `gtkmm3` alone; historical Linux runtime budget 100-300 MiB |
| PySide6/Qt + shiboken6 | Optional desktop tools only | Not needed by Module 01 | 1.1 GiB + 1.4 MiB measured, excluding external OS libraries |
| NumPy | Optional desktop tools only | Not needed by Module 01 | 34 MiB measured |
| pyqtgraph | Optional desktop tools only | Not needed by Module 01 | 9.1 MiB measured, excluding NumPy/Qt already listed |
| argcomplete | Install into environment | Keep for current launcher | 0.25 MiB measured |
| Display/remote desktop stack | Not needed to compile | Not needed by the normal tutorial | Historical 100-300 MiB Linux budget for Xvfb/VNC/noVNC, browser excluded |

The original desktop Python virtual environment measured **1.3 GiB**, and its all-module build directory measured **20 MiB** (includes build intermediates, not just deliverable binaries). These overlap the table entries: do not add them again. The SDK contains the C++ library and wheel directories, and many system libraries are shared. A deployment also needs application source/assets, generated `Types.py`, and XML configuration. A Linux runtime image total cannot be inferred by summing these Mac measurements.

### Cloud Eval Packaging And Startup

The web-only recipe adds about 20.5 MB of filesystem layers over the base. The original Playground image dominates the total footprint. Precompilation can additionally remove per-session builds; that startup optimization has not been implemented.

Recommended candidate: build in CI using a multi-stage container build, then copy the Linux/architecture-compatible Module 01 binaries, generated Python types, source/assets/configuration, installed Python environment, audited shared-library closure, and Markdown tutorial into a versioned runtime image. Keep the compiler, SDK build tools, headers, package caches, and unrelated modules in the builder stage. Build and runtime must match the target OS, CPU architecture, ABI, Python version, and Connext version; the local Mac binaries are not Linux deliverables.

Two deployment options need platform-team agreement:

- **Dedicated runtime workspace image:** simplest co-location of apps and IDE, but still a second image to maintain, patch, distribute, and prewarm. It requires platform support and is not just a new workspace definition.
- **Application container alongside the existing workspace:** could keep application build/runtime packages out of the base IDE image, but shifts their size into another image rather than eliminating it. Requires supported container orchestration, browser port routing for 8090-8093, DDS networking/discovery configuration, licensing, and process lifecycle management. Do not assume users can start Docker inside the workspace or that DDS discovery works across container networks by default.

Neither prebuilt packaging option is supplied by this repository today. `launch_all.sh` checks the pinned submodule and runs the build. Local setup installs Python packages; cloud mode reuses the image environment. For a provisioned environment, `./tutorial/run_digital_or.sh --launch-only --web` skips setup/build and launches only the demo; it still expects the configured virtual environment, `NDDSHOME`, compatible binaries, generated types, configuration, and runtime libraries.

Before committing to either option, measure on the actual Linux base image: dependency-by-dependency incremental installed size, compressed registry layers to pull, uncompressed image size, and cold versus warm time to the first usable tutorial and all four responsive web UIs. Compare against the base workspace and separate image pull/unpack, provisioning, and application startup. Preinstalling removes session downloads/builds; larger uncached layers can still increase cold startup significantly. Reusing cached base layers and prewarming may help, but no startup-time claim is established yet. Pin the final Python/system dependencies and image digest so size, startup, and maintenance costs are reproducible.

## Run locally

```bash
git clone git@github.com:sagmua/rti_cloud_eval_medtech.git
cd rti_cloud_eval_medtech
./tutorial/launch_all.sh --vscode
```

The single launch command initializes the MedTech submodule if missing, prepares local Python dependencies, builds native apps and Python types, and opens a 2x2 device grid. Open [the tutorial](tutorial/TUTORIAL.md) for guided steps. A source checkout at another commit blocks launch rather than being reset; align it explicitly without discarding local work.

The default mode is `--cloud`; it requires a provisioned extension, explicit public `MEDTECH_CLOUD_URL`, and offline image dependencies. Use `--vscode` for desktop VS Code or `--web` for local browser tabs. Add `--secure` only after generating the artifacts described in the MedTech README. Stop with `./tutorial/stop_all.sh`, or relaunch with `./tutorial/restart_all.sh` and the same mode options.

## Verify a clean clone

After initialization, `git submodule status -- medtech-reference-architecture` must report the recorded pin without a leading `-` or `+`. Check four responsive device UIs, Patient Sensor, and live DDS data. The first launch builds applications; later launches reuse the build.

See [local usage](tutorial/README.md) and [cloud integration constraints](tutorial/INTEGRATION_NOTES.md). Prebuilt packaging remains a proposal. Hosted integration requires licensed runtime support and authenticated browser port routing, not a display server; live acceptance remains outstanding.
