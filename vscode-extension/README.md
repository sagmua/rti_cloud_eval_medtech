# MedTech Device Grid

The extension opens Arm Controller / Orchestrator above Arm / Patient Monitor in
a 2x2 VS Code editor grid. It has no tutorial panel, activity-bar container, or
tutorial content. In the MedTech helper workspace, read `tutorial/TUTORIAL.md`.

This extension belongs to the MedTech helper, not the reference-architecture
submodule. Cloud provisioning links the helper's extension into the code-server extensions
directory before IDE startup. The launcher checks its activation acknowledgment
before building. A fresh workspace should not require a reload; manually updating
a running extension host may require one. Desktop startup still uses VSIX packaging.

Closing a device editor tab stops its owned DDS process. Orchestrator `Start`
resumes paused devices or relaunches stopped devices without replacing surviving
tabs. The Command Palette's **Digital Operating Room: Open Orchestrator** command
recovers Orchestrator itself. Full demo shutdown stops recovered process groups,
closes the grid, and restores the previous empty-editor-group preference.

`--web` mode opens ordinary browser tabs without extension-managed recovery.

```bash
npm test --prefix vscode-extension
python3 -m pytest tests
```

This extension receives URLs emitted by `tutorial/medtech_grid.py` and opens each
Digital Operating Room UI in editor tabs. Cloud tutorial content uses the
platform walkthrough or Markdown, not an extension-owned side panel.

## What it does

- Opens Arm Controller, Surgical Arm Monitor, Orchestrator, and Patient Monitor in a 2x2 editor grid.
- Closes only these MedTech web tabs when the launcher exits, including after `Ctrl+C`.
- Closing a device tab manually kills its launcher-owned process, stopping DDS heartbeats.
	Keep Orchestrator open to observe the disconnect; select the device and use **Start**
	to relaunch it and reopen its tab. Start also resumes paused devices. Patient Sensor
	can be restarted without a tab. Plain browser tabs (`--web`) do not have launcher recovery.
- Use **Digital Operating Room: Open Orchestrator** in the Command Palette if the
  Orchestrator itself was closed or stopped. The full demo must have been launched first.
- Accepts only HTTP(S) URLs hosted at `localhost`, `127.0.0.1`, or `::1`.

## Install or update

Run these commands from the repository root to build the extension archive:

```bash
cd vscode-extension
npm ci --ignore-scripts --no-audit --no-fund
npm run package
```

1. Run **Extensions: Install from VSIX...** from the Command Palette.
2. Select `medtech-web-tabs-0.1.2.vsix` from this directory.
3. Reload the VS Code window when prompted.

Rebuild and reinstall the VSIX after changing `extension.js` or `package.json`.

## Run the demo

From the repository root:

```bash
./tutorial/launch_all.sh --vscode
```

The helper starts the web apps and opens four tabs in the configured grid.
Use `./tutorial/stop_all.sh` to stop the background demo. For an already built
foreground session, run `./tutorial/run_digital_or.sh --launch-only --vscode`;
`Ctrl+C` then stops its applications and closes their tabs.

## Cloud IDE

Open the provisioned browser IDE, trust the workspace, and run
`./tutorial/launch_all.sh --cloud` from `/config/workspace`.
Set `MEDTECH_CLOUD_URL` in the container environment before the extension host
starts. It must include the external IDE prefix, for example
`https://eval.example.test/workspaces/cpg-generated/ide`. There is no implicit
localhost fallback. Select the intended IDE window when multiple windows are open.

Device frames use authenticated code-server `/proxy/<port>/` routes. Launcher
requests, readiness, sensor state, tab ownership, and close tokens share a
temporary directory scoped by UID and the canonical source checkout's SHA-256
prefix. Unrelated workspace folders do not start monitoring or claim requests.
A single focused extension host for that checkout consumes requests. No
desktop `vscode://` URI handler is needed. Device recovery is controlled by Orchestrator
Start, not a tutorial sidebar. After setup, `launch_all.sh` runs the demo in the
background and verifies all four HTTP applications. Use `./tutorial/stop_all.sh` to stop
it or `./tutorial/restart_all.sh --cloud` to restart it. Closing a terminal or separate
browser page does not stop the background demo.

## Troubleshooting

- Tabs open in a browser: install the VSIX and reload VS Code; `--vscode` needs this extension to receive the launcher URI.
- Layout is stale: close the existing MedTech tabs, reload VS Code, and launch again.
- A webview is blank: confirm the launcher is still running and that the corresponding localhost port is available.