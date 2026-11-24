# Digital Operating Room for RTI Cloud Evaluation

This repository is the Cloud Evaluation companion to the [RTI Connext MedTech Reference Architecture](https://github.com/rticommunity/rticonnextdds-medtech-reference-architecture). Its Digital Operating Room demo (Module 01) shows how simulated medical devices written in C++ and Python exchange vitals, motor commands, and device status over Connext DDS using shared XML data types and QoS.

![Digital Operating Room data flows](https://raw.githubusercontent.com/rticommunity/rticonnextdds-medtech-reference-architecture/2f5b883d6f92a8ecef16f545f07f68f7371ccbb6/resource/images/module-01-diagram-digital-OR.svg)

- **Patient Sensor** publishes simulated vitals in the background. **Patient Monitor** displays them as live readings and waveforms.
- **Arm Controller** sends commands to the **Arm**, a simulated five-joint surgical robot.
- **Orchestrator** tracks device health and lets you pause, shut down, and restart devices.

The included VS Code extension displays the four device interfaces in a 2×2 editor grid. The simulator is for evaluation, not clinical use.

## Run the demo

**In RTI Cloud Evaluation:** Follow the walkthrough on the right, starting with **Launch the Operating Room**. It provides the commands and guides you through vitals, arm control, and device recovery.

**Outside Cloud Evaluation:** See [Run the demo locally](docs/local-demo.md) for prerequisites and commands.
