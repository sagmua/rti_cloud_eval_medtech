# Digital Operating Room Tutorial

The guided tutorial lives in [TUTORIAL.md](TUTORIAL.md). Open it in a Markdown
viewer alongside the four device UIs in a 2x2 VS Code editor grid. The bundled
device-grid extension has no tutorial panel. Hosted template integration is not
yet validated.

## Files

- [TUTORIAL.md](TUTORIAL.md): the ten guided tutorial steps and source links.
- [INTEGRATION_NOTES.md](INTEGRATION_NOTES.md): hosted deployment requirements.
- [launch_all.sh](launch_all.sh): initialize the pinned submodule if absent, set up, build,
  and start all five applications in the background.
- [run_digital_or.sh](run_digital_or.sh): existing setup/build and foreground launch helper.
- [medtech_grid.py](medtech_grid.py): helper-owned grid/IPC process adapter; reuses
  application commands from the source instead of requiring extension hooks there.
- [stop_all.sh](stop_all.sh): stop this checkout's demo processes without stopping
  the browser IDE or container.
- [restart_all.sh](restart_all.sh): stop and relaunch; forwards launcher options.

## Local Demo

Run from the repository root with licensed Connext 7.7 installed:

```bash
git clone git@github.com:sagmua/rti_cloud_eval_medtech.git
cd rti_cloud_eval_medtech
./tutorial/launch_all.sh --vscode
```

The launcher initializes the pinned submodule, prepares a virtual environment,
builds C++ and Python type support, and opens Orchestrator, Arm Controller, Arm,
and Patient Monitor in a 2x2 editor grid. Patient Sensor is headless. Desktop VS
Code mode packages/installs the bundled device extension using Node.js/npm and
the `code` CLI; `--web` opens ordinary browser tabs without those dependencies.
Add `--secure` only after generating the
security artifacts described in the [source setup guide](../medtech-reference-architecture/README.md).

## Cloud Workspace

RTI Cloud owns the hosted Playground image. It supplies `/opt/medtech-venv`,
the existing licensed Connext 7.7 Python API, and an offline view of the SDK's CMake utilities.
Provisioning initializes the MedTech submodule, preserves the complete
wrapper/Git metadata, and links this helper's versioned extension before
code-server starts. No npm, pip, or source dependency download occurs at launch.

Open the provisioned IDE, accept Workspace Trust, open
[TUTORIAL.md](TUTORIAL.md), and run in its terminal:

```bash
cd /config/workspace
./tutorial/launch_all.sh --cloud
```

Cloud mode is the default. It checks extension activation before building and
opens Arm Controller / Orchestrator above Arm / Patient Monitor in the editor grid.
A fresh provisioned workspace should not require an IDE reload; an already
running IDE upgraded manually may need one. No tutorial panel or activity-bar icon is registered. Select the
intended IDE window before launching if multiple windows are open. The printed
proxy URLs are also available for ordinary browser tabs. For example, with
`MEDTECH_CLOUD_URL=https://eval.example.test/workspaces/cpg-generated/ide`:

- Orchestrator: `<MEDTECH_CLOUD_URL>/proxy/8090/`
- Arm Controller: `<MEDTECH_CLOUD_URL>/proxy/8091/`
- Arm: `<MEDTECH_CLOUD_URL>/proxy/8092/`
- Patient Monitor: `<MEDTECH_CLOUD_URL>/proxy/8093/`

Only the authenticated code-server port needs publishing. Set
`MEDTECH_CLOUD_URL` in the container environment before IDE startup, including
the public path prefix. There is no implicit localhost fallback. Hosted
deployments must validate matching proxy routing and keep platform authentication
in front of every proxy route. IPC/ownership state is scoped to the canonical
source checkout, so unrelated IDE folders cannot consume launch requests.

## Stop And Restart

After setup, the terminal prompt returns while the demo runs in the background.
The launcher prints the supervisor PID and log path. Closing a terminal or browser
tab does not stop the applications in `--web` mode. Closing a device editor tab
in grid mode stops its DDS process; Orchestrator `Start` resumes paused devices
or relaunches stopped devices and reopens their tabs. Use **Digital Operating
Room: Open Orchestrator** in the Command Palette to recover Orchestrator itself.
Stop or restart the complete demo with:

```bash
./tutorial/stop_all.sh
./tutorial/restart_all.sh --cloud
```

Use `./tutorial/restart_all.sh --web` for local browser mode, and add `--secure`
when needed. Stop targets only this checkout's processes owned by your user and
is safe to run again when nothing is running. Stop closes device editor tabs;
ordinary browser tabs remain open and need refreshing after restart. Do not
launch a second copy while the first is running.
A ports-already-in-use error means the existing launch must first be stopped.
