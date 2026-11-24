# Digital Operating Room device grid

This MedTech extension opens the Orchestrator, Arm Controller, Arm, and Patient Monitor as a 2×2 editor grid. Patient Sensor is headless. See the [local run guide](../docs/local-demo.md) for desktop setup.

- **Desktop:** `./scripts/medtech.sh start --vscode` packages and installs the extension before launching the simulator. Add `--secure` for the upstream DDS Security demo.
- **Cloud Evaluation:** The platform loads the extension before IDE startup. `./scripts/medtech.sh start --cloud` opens the device grid through the authenticated IDE proxy.
- **Recovery:** **Digital Operating Room: Open Orchestrator** reopens the Orchestrator panel. Select an offline device there and click **Start** to restore it.

Run `npm test` in this directory to test the extension.
