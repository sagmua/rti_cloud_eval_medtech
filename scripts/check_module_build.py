"""Validate Module 01 restart prerequisites without building or launching apps."""

import os
from pathlib import Path
import sys


def check(source, secure):
    sys.path.insert(0, str(source / "resource/python"))
    from scripts import platform_setup

    build = "./scripts/medtech.sh build" + (" --secure" if secure else "")
    generated_types = source / "modules/01-operating-room/src/Types.py"
    if not generated_types.is_file():
        raise SystemExit(f"error: generated Python types are missing; run {build} first.")

    for app in ("Orchestrator", "ArmController", "PatientSensor"):
        try:
            executable = Path(platform_setup.find_executable(app))
        except FileNotFoundError:
            raise SystemExit(f"error: {app} binary is missing; run {build} first.") from None
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise SystemExit(f"error: {executable} is not executable; run {build} first.")

    if secure:
        module = source / "modules/01-operating-room"
        security = module / (os.environ.get("RTI_SECURITY_ARTIFACTS_DIR") or "../../system_arch/security")
        scope = Path("domain_scope/OperationalDomain")
        required = [
            Path("ca") / ca / "certs/TrustedRootCa" / f"{ca}.crt"
            for ca in ("TrustedPermissionsCa", "TrustedIdentityCa")
        ]
        required.extend([
            scope / "OperationalDomain.psk",
            scope / "governance/OperationalDomain/signed/TrustedPermissionsCa/OperationalDomain.p7s",
        ])
        identities = (
            ("Arm", "Arm"), ("ArmController", "ArmController"),
            ("Orchestrator", "Orchestrator"), ("Orchestrator", "SecureLogReader"),
            ("PatientSensor", "PatientSensor"), ("PatientMonitor", "PatientMonitor"),
        )
        for app, identity in identities:
            directory = Path("identity/operating-room") / app / identity
            required.extend([
                directory / "certs/TrustedIdentityCa" / f"{identity}.chain.pem",
                directory / "private" / f"{identity}.key",
                scope / "permissions" / identity / "signed/TrustedPermissionsCa" / f"{identity}.p7s",
            ])
        for artifact in required:
            if not (security / artifact).is_file() or not os.access(security / artifact, os.R_OK):
                raise SystemExit(f"error: required DDS Security artifact unavailable: {artifact}; run {build} first.")


if __name__ == "__main__":
    check(Path.cwd(), secure=sys.argv[1] == "1")
