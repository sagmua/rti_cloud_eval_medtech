# Integration Notes: Digital Operating Room Cloud Eval

Open requirements before this demo becomes an `evaluation.rti.com` workspace
template. The tutorial is [TUTORIAL.md](TUTORIAL.md), not an injected tutorial panel.

## Browser Routing

The demo has four HTTP UIs on ports 8090-8093 and a headless Patient Sensor.
Cloud mode uses the bundled device-only extension to embed authenticated
code-server proxy URLs in a 2x2 editor grid. Desktop `--vscode` mode uses the
same grid; `--web` opens ordinary browser tabs. Validate extension activation,
those proxy routes, authentication, and any deployment URL prefix in the hosted
workspace. No desktop display or tutorial panel is needed. Device editor tab
closure stops its DDS process; ordinary browser tab closure does not.

## Build And Licensing

The workspace needs licensed Connext Professional 7.7 with `NDDSHOME` set,
Python runtime dependencies, CMake >=3.17, and a C++17 compiler if building there.
Module 01 needs no GTK or Qt dependencies. The helper runs
`python3 build.py -- --target module-01`; on CLOUD-701 that target includes
`refArchTypesPy`, so both native binaries and Python types are generated without
building the other modules.

RTI Cloud's Playground image owns hosted packaging and exposes the installed SDK
CMake modules through `/opt/medtech-deps/connext-cmake-utils/cmake/Modules`.
The helper supplies `FETCHCONTENT_SOURCE_DIR_RTICONNEXTDDS-CMAKE-UTILS` to bypass
the source's normal Git download. CLOUD-701 needs no separate JSON dependency.
The [historical image runbook](../docker/README_cloud_eval_image.md) is not
the hosted recipe. Prebuilt Linux applications could eliminate per-session
builds, but a compatible runtime layout, licensing, redistribution rights, and
cold/warm startup measurements still need validation. Do not copy macOS build
outputs or virtual environments into a Linux workspace.

## Template Rollout

1. Include the Markdown tutorial and pinned source in the workspace.
2. Validate provisioning, licensed runtime, all four proxy routes, live DDS data,
   pause/resume, and scoped stop/restart on a fresh hosted workspace.
3. Register the workspace template through RTI's platform team. Existing Connext
   Studio visualization tools may be offered separately; they are not required
   to render this tutorial.

The local pilot integration expects the exact helper HTTPS URL and the complete
repository (`repo_path="/"` or unset). Both manager and operator must explicitly enable
the fork with `CDB_ENVIRONMENT=medtech_pilot` and
`WORKSPACE_MEDTECH_DEV_REPO_URL=https://github.com/sagmua/rti_cloud_eval_medtech.git`.
No production deployment is enabled. The source gitlink now selects published
`feature/CLOUD-701` commit `1c3de45f3b21f1964b6472f45c56128d71692be9`, without local
source patches or an upstream extension. This helper owns `vscode-extension/`
and `tutorial/medtech_grid.py`. Publish the reviewed helper revision/tag before
enabling it in the frontend; uncommitted helper files cannot be cloned by a hosted
workspace. The gitlink is authoritative; do not use `submodule update --remote`
during normal provisioning.