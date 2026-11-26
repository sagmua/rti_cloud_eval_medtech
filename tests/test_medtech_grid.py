import importlib.util
import json
import os
import signal
import subprocess
import sys
import threading
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("medtech_grid", ROOT / "scripts/medtech_grid.py")
grid = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grid)


@pytest.fixture(autouse=True)
def isolate_grid(monkeypatch, tmp_path):
    monkeypatch.setenv("MEDTECH_CLOUD", "1")
    monkeypatch.setattr(grid.tempfile, "gettempdir", lambda: str(tmp_path))


def test_cloud_grid_queues_uris_without_upstream_extension_hooks():
    uri = "vscode://rti.medtech-web-tabs/session?secure=1"
    grid._open_vscode_uri(uri)
    requests = list((grid._tab_state_dir() / "requests").iterdir())
    assert len(requests) == 1
    assert json.loads(requests[0].read_text()) == {"uri": uri}
    assert requests[0].suffix == ".json"


def test_state_is_scoped_to_canonical_source_root(monkeypatch, tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    monkeypatch.setattr(grid, "PROJECT_ROOT", first)
    state = grid._tab_state_dir()
    alias = tmp_path / "alias"
    alias.symlink_to(first, target_is_directory=True)
    monkeypatch.setattr(grid, "PROJECT_ROOT", alias)
    assert grid._tab_state_dir() == state
    monkeypatch.setattr(grid, "PROJECT_ROOT", second)
    assert grid._tab_state_dir() != state


def test_grid_waits_for_http_state_before_opening_owned_tab(monkeypatch):
    probes, uris = [], []

    def urlopen(url, timeout):
        probes.append(url)
        if len(probes) == 1:
            raise ConnectionRefusedError()
        return nullcontext(SimpleNamespace(status=200))

    monkeypatch.setattr(grid.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(grid, "_open_vscode_uri", uris.append)
    grid._open_when_ready("http://localhost:8092/", "Arm", "a" * 32, threading.Event())
    assert probes == ["http://localhost:8092/api/state"] * 2
    uri = urlsplit(uris[0])
    assert uri.netloc == "rti.medtech-web-tabs"
    assert uri.path == "/open"
    assert parse_qs(uri.query) == {
        "url": ["http://localhost:8092/"], "title": ["Arm"], "closeToken": ["a" * 32],
    }


def test_stopped_launch_does_not_open_a_tab(monkeypatch):
    stopped = threading.Event()
    stopped.set()
    monkeypatch.setattr(grid, "_open_vscode_uri", lambda uri: pytest.fail(uri))
    grid._open_when_ready("http://localhost:8092/", "Arm", "a" * 32, stopped)


def test_tab_close_kills_only_its_exact_child(tmp_path):
    children = [
        subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        for _ in range(2)
    ]
    token = "b" * 32
    (tmp_path / f"{token}.close").touch()
    closed = set()
    try:
        grid._watch_tab_closures(children[:1], {0: token}, threading.Event(), tmp_path, closed=closed)
        assert children[0].wait(timeout=5) == -signal.SIGKILL
        assert children[1].poll() is None
        assert closed == {0}
    finally:
        grid._shutdown(children)


def test_exited_child_closes_only_its_owned_tab(monkeypatch, tmp_path):
    uris = []
    monkeypatch.setattr(grid, "_open_vscode_uri", uris.append)
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait(timeout=5)
    token = "c" * 32
    grid._watch_tab_closures([child], {0: token}, threading.Event(), tmp_path)
    assert uris == [f"vscode://rti.medtech-web-tabs/close-owned?closeToken={token}"]


@pytest.mark.parametrize("failure", [OSError("spawn failed"), KeyboardInterrupt(), SystemExit(7)])
def test_partial_launch_reaps_children_and_preserves_error(monkeypatch, tmp_path, failure):
    popen = subprocess.Popen
    owned = []
    unrelated = popen([sys.executable, "-c", "import time; time.sleep(60)"])

    def spawn(*args, **kwargs):
        if owned:
            raise failure
        child = popen(*args, **kwargs)
        owned.append(child)
        return child

    monkeypatch.setattr(grid.subprocess, "Popen", spawn)
    command = [sys.executable, "-c", "import time; time.sleep(60)"]
    try:
        with pytest.raises(type(failure)) as caught:
            grid._launch([command, command], tmp_path, os.environ.copy(), web_urls=[])
        assert caught.value is failure
        assert owned[0].returncode is not None
        assert unrelated.poll() is None
    finally:
        grid._shutdown([*owned, unrelated])


def test_cleanup_failure_does_not_skip_other_children_or_mask_launch_error(monkeypatch, tmp_path, capsys):
    failure = OSError("third spawn failed")
    popen = subprocess.Popen
    children = []

    def spawn(*args, **kwargs):
        if len(children) == 2:
            raise failure
        child = popen(*args, **kwargs)
        children.append(child)

        def terminate():
            raise OSError("terminate failed")

        if len(children) == 1:
            monkeypatch.setattr(child, "terminate", terminate)
        return child

    monkeypatch.setattr(grid.subprocess, "Popen", spawn)
    command = [sys.executable, "-c", "import time; time.sleep(60)"]
    with pytest.raises(OSError) as caught:
        grid._launch([command, command, command], tmp_path, os.environ.copy(), web_urls=[])
    assert caught.value is failure
    assert children[0].returncode == -signal.SIGKILL
    assert children[1].returncode is not None
    assert "terminate failed" in capsys.readouterr().err


@pytest.mark.parametrize("security", [False, True])
def test_grid_cli_reuses_upstream_commands_and_web_urls(monkeypatch, tmp_path, security):
    commands = [["/bin/ArmController", "--port", "8091"], ["/bin/PatientSensor"]]
    env = {"NDDSHOME": "/installed-sdk"}
    resolved, launched = [], []

    def resolve(*args):
        resolved.append(args)
        return commands, tmp_path, env

    reference = SimpleNamespace(
        _resolve_module=resolve,
        _web_urls=lambda specs: [("ArmController", "http://localhost:8091/")]
        if specs[0][0][0][0] == "/bin/ArmController" else [],
    )
    monkeypatch.setitem(sys.modules, "launch", reference)
    monkeypatch.setattr(sys, "argv", ["medtech_grid.py", "ArmController", *(["--security"] if security else [])])
    monkeypatch.setattr(grid, "_launch", lambda *args, **kwargs: launched.append((args, kwargs)))
    grid.main()
    assert resolved == [("01-operating-room", ["ArmController"], security)]
    assert launched == [((commands, tmp_path, env), {
        "web_urls": [(0, "ArmController", "http://localhost:8091/")], "keep_alive": False,
    })]


@pytest.mark.parametrize("stop_signal", [signal.SIGINT, signal.SIGTERM])
def test_full_grid_supervisor_stays_alive_after_devices_exit(tmp_path, stop_signal):
    code = (
        "import os,sys; from pathlib import Path; "
        f"sys.path.insert(0, {str(ROOT / 'scripts')!r}); import medtech_grid as grid; "
        "grid._open_vscode_uri = lambda uri: None; "
        "print('ready', flush=True); "
        "grid._launch([[sys.executable, '-c', 'pass']], Path.cwd(), "
        "os.environ.copy(), web_urls=[], keep_alive=True)"
    )
    supervisor = subprocess.Popen(
        [sys.executable, "-c", code], cwd=tmp_path, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True,
    )
    try:
        assert supervisor.stdout.readline().strip() == "ready"
        with pytest.raises(subprocess.TimeoutExpired):
            supervisor.wait(timeout=0.3)
        supervisor.send_signal(stop_signal)
        _, error = supervisor.communicate(timeout=5)
        # The adapter's CLI catches the interrupt; this direct function call exposes it.
        assert "KeyboardInterrupt" in error
    finally:
        if supervisor.poll() is None:
            supervisor.kill()
        supervisor.wait(timeout=5)
        supervisor.stdout.close()
        supervisor.stderr.close()


@pytest.mark.parametrize("keep_alive", [False, True])
def test_crashed_device_is_reported_once_without_stopping_healthy_devices(
    monkeypatch, tmp_path, capsys, keep_alive,
):
    healthy = Mock(args=["Orchestrator"])
    healthy.poll.return_value = None
    crashed = Mock(args=["Arm.py"])
    crashed.poll.return_value = -9
    monkeypatch.setattr(grid.subprocess, "Popen", Mock(side_effect=[healthy, crashed]))
    ticks = 0

    def interrupt_after_two_ticks(_):
        nonlocal ticks
        healthy.terminate.assert_not_called()
        ticks += 1
        if ticks == 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(grid.time, "sleep", interrupt_after_two_ticks)
    with pytest.raises(KeyboardInterrupt):
        grid._launch(
            [["Orchestrator"], ["Arm.py"]], tmp_path, {},
            web_urls=[], keep_alive=keep_alive,
        )
    assert ticks == 2
    assert capsys.readouterr().err.count("Application exited with code -9: ['Arm.py']") == 1
    healthy.terminate.assert_called_once()
    healthy.wait.assert_called_once()


@pytest.mark.parametrize("mode,expected", [
    ("--vscode", ["medtech_grid.py", "Arm", "--security"]),
    ("--web", ["launch.py", "01-operating-room", "Arm", "--security"]),
])
def test_helper_routes_grid_and_browser_modes_without_legacy_upstream_flags(tmp_path, mode, expected):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    runner = scripts / "run_module.sh"
    runner.write_text((ROOT / "scripts/run_module.sh").read_text())
    source = tmp_path / "medtech-reference-architecture"
    (source / ".venv/bin").mkdir(parents=True)
    (source / "launch.py").touch()
    (source / ".venv/bin/activate").write_text(":\n")
    tools = tmp_path / "tools"
    tools.mkdir()
    python = tools / "python3"
    python.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    python.chmod(0o755)
    result = subprocess.run(
        ["bash", str(runner), "--launch-only", mode, "Arm", "--secure"],
        capture_output=True, text=True,
        env={**os.environ, "NDDSHOME": str(tmp_path), "MEDTECH_VENV": str(source / ".venv"),
             "PATH": str(tools) + os.pathsep + os.environ["PATH"]},
    )
    assert result.returncode == 0, result.stderr
    arguments = result.stdout.splitlines()[1:]
    arguments[0] = Path(arguments[0]).name
    assert arguments == expected


@pytest.mark.parametrize("command", ["build", "start", "stop", "restart"])
def test_public_lifecycle_commands_support_help(command):
    result = subprocess.run(
        [str(ROOT / "scripts/medtech.sh"), command, "--help"],
        capture_output=True, text=True, check=True,
    )
    assert "Usage:" in result.stdout
    assert not result.stderr


@pytest.mark.parametrize(
    "secure, check_status, stop_status, expected",
    [
        (False, 0, 0, ["--check-launch", "stop", "--launch-only --web"]),
        (True, 0, 0, ["--check-launch --secure", "stop", "--launch-only --web --secure"]),
        (True, 1, 0, ["--check-launch --secure"]),
        (False, 0, 1, ["--check-launch", "stop"]),
    ],
)
def test_restart_preflights_then_relaunches_without_setup(tmp_path, secure, check_status, stop_status, expected):
    scripts = tmp_path / "scripts"
    tools = tmp_path / "tools"
    source = tmp_path / "medtech-reference-architecture"
    for directory in (scripts, tools, source):
        directory.mkdir()
    (source / ".git").touch()
    (source / "launch.py").touch()
    wrapper = scripts / "medtech.sh"
    wrapper.write_text((ROOT / "scripts/medtech.sh").read_text())

    def stub(path, code):
        path.write_text("#!/bin/bash\n" + code + "\n")
        path.chmod(0o755)

    stub(tools / "git", "echo fixture-pin")
    stub(tools / "python3", 'if [[ $# == 2 ]]; then for i in {1..50}; do '
         'grep -q "^--launch-only" "$TRACE" && exit 0; sleep 0.02; done; exit 1; fi')
    stub(scripts / "run_module.sh", 'echo "$*" >> "$TRACE"; '
         'case "$1" in --check-launch) exit "$CHECK_STATUS";; --launch-only) exit 0;; *) exit 97;; esac')
    stub(scripts / "stop.sh", 'echo stop >> "$TRACE"; exit "$STOP_STATUS"')

    trace = tmp_path / "trace"
    result = subprocess.run(
        ["bash", str(wrapper), "restart", "--web", *(["--secure"] if secure else [])],
        capture_output=True, text=True, timeout=10,
        env={**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"],
             "TRACE": str(trace), "CHECK_STATUS": str(check_status), "STOP_STATUS": str(stop_status)},
    )
    assert result.returncode == (check_status or stop_status), result.stderr
    assert trace.read_text().splitlines() == expected


def test_wrapper_does_not_reset_a_different_existing_source(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    source = tmp_path / "medtech-reference-architecture"
    source.mkdir()

    def git(directory, *args):
        return subprocess.check_output(["git", "-C", str(directory), *args], text=True).strip()

    git(tmp_path, "init")
    git(source, "init")
    (source / "notes.txt").write_text("Pinned")
    git(source, "add", ".")
    identity = ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.test"]
    git(source, *identity, "commit", "-m", "Pinned")
    pinned = git(source, "rev-parse", "HEAD")
    git(tmp_path, "update-index", "--add", "--cacheinfo", f"160000,{pinned},medtech-reference-architecture")
    (source / "notes.txt").write_text("Preserve")
    git(source, *identity, "commit", "-am", "User revision")
    current = git(source, "rev-parse", "HEAD")
    script = scripts / "medtech.sh"
    script.write_text((ROOT / "scripts/medtech.sh").read_text())
    tools = tmp_path / "tools"
    tools.mkdir()
    python = tools / "python3"
    python.write_text("#!/bin/sh\nexit 0\n")
    python.chmod(0o755)
    result = subprocess.run(
        ["bash", str(script), "build", "--web"], text=True, capture_output=True,
        env={**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"]},
    )
    assert result.returncode != 0
    assert "does not match the recorded source pin" in result.stderr
    assert git(source, "rev-parse", "HEAD") == current
    assert (source / "notes.txt").read_text() == "Preserve"


def test_stop_only_stops_this_helpers_grid_and_can_run_twice(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    stop = scripts / "stop.sh"
    stop.write_text((ROOT / "scripts/stop.sh").read_text())
    (scripts / "medtech_grid.py").write_text(
        "import sys; print('ready', flush=True); sys.stdin.buffer.read()"
    )
    unrelated = tmp_path / "unrelated/medtech_grid.py"
    unrelated.parent.mkdir()
    unrelated.write_text((scripts / "medtech_grid.py").read_text())
    children = []
    env = {**os.environ, "MEDTECH_CLOUD": "0",
           "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"]}
    try:
        for script in [scripts / "medtech_grid.py", unrelated]:
            child = subprocess.Popen(
                [sys.executable, str(script)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
            )
            children.append(child)
            assert child.stdout.readline().strip() == "ready"
        result = subprocess.run(["bash", str(stop)], capture_output=True, text=True, check=True, env=env)
        assert "Stopped 1" in result.stdout
        assert children[0].wait(timeout=5) != 0
        assert children[1].poll() is None
        result = subprocess.run(["bash", str(stop)], capture_output=True, text=True, check=True, env=env)
        assert "No Digital Operating Room processes running" in result.stdout
        assert children[1].poll() is None
    finally:
        grid._shutdown(children)
        for child in children:
            child.stdin.close()
            child.stdout.close()
