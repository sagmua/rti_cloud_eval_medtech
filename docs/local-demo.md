# Run the Digital Operating Room locally

Start with the [demo overview](../README.md). Run the commands below from the companion repository root.

## Start the demo

You need a licensed RTI Connext Professional 7.7.0 installation with target libraries, a C++ compiler, CMake, Git, and Python 3.10 or later compatible with the installed Connext Python wheel. Make that interpreter available as `python3`, then source the SDK's `rtisetenv_<arch>.bash`. Clone with `--recurse-submodules` or initialize the pinned source with `git submodule update --init --recursive`.

```sh
./scripts/medtech.sh build            # Optional; start also runs the build
./scripts/medtech.sh start --vscode    # Desktop VS Code and Node.js/npm required
# Or use local browser tabs instead:
./scripts/medtech.sh start --web
```

To try DDS Security on a desktop installation with the Security Plugins and OpenSSL tools, use `./scripts/medtech.sh start --vscode --secure` for a first launch. If the demo is already running, run `./scripts/medtech.sh build --secure` to prepare the demo credentials, then `./scripts/medtech.sh restart --vscode --secure` to switch modes. Do not use these credentials in production.

All starts run in the background after readiness checks. Use `./scripts/medtech.sh stop`; closing the terminal or a standalone browser tab does not stop the demo. Use `./scripts/medtech.sh restart` with your display and security flags to reload runtime XML without rebuilding. After changing C++ code or DDS types, run `./scripts/medtech.sh build` before restarting. Run `./scripts/medtech.sh --help` for options.

## Explore

1. **Follow live vitals.** In Orchestrator select **Patient Sensor**, click **Pause**, and watch the Patient Monitor stop receiving fresh data. Click **Start** to resume.
2. **Move the simulated arm.** Click **AUTO** on one joint in Arm Controller and watch the Arm panel. Click it again or use **Stop All**. Use **+** and **−** to jog a joint.
3. **Observe and recover a device.** In the VS Code grid, close the Arm device tab and watch Orchestrator mark Arm offline while the other devices keep running. Select **Arm** and click **Start** to reopen it. In browser mode, use Orchestrator **Shut Down** to observe the offline state and restart the whole demo with the terminal command.
4. **Read the shared model.** Open `system_arch/Types.xml` and `system_arch/qos/Qos.xml` in the pinned submodule. Trace the C++ publisher and Python subscriber, the arm control topic, and the heartbeat deadline and device-addressed commands in the [upstream Module 01 guide](https://github.com/rticommunity/rticonnextdds-medtech-reference-architecture/tree/2f5b883d6f92a8ecef16f545f07f68f7371ccbb6/modules/01-operating-room).
