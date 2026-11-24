#!/usr/bin/env python3
"""Adapt the reference architecture's application commands to the helper's IDE grid."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1] / "medtech-reference-architecture"


def _tab_state_dir() -> Path:
    state = Path(tempfile.gettempdir()) / f"medtech-web-tabs-{os.getuid()}"
    if os.environ.get("MEDTECH_CLOUD") == "1" or Path("/app/code-server").exists():
        state /= hashlib.sha256(str(PROJECT_ROOT.resolve()).encode()).hexdigest()[:16]
    return state


def _open_vscode_uri(uri: str) -> None:
    if os.environ.get("MEDTECH_CLOUD") == "1":
        requests = _tab_state_dir() / "requests"
        requests.mkdir(parents=True, exist_ok=True)
        request = requests / f"{time.time_ns()}-{uuid.uuid4().hex}.json"
        pending = request.with_suffix(".tmp")
        pending.write_text(json.dumps({"uri": uri}))
        pending.replace(request)
    elif platform.system() == "Darwin":
        subprocess.run(["open", "-a", "Visual Studio Code", uri], check=True)
    elif not webbrowser.open(uri):
        raise RuntimeError("Unable to dispatch the MedTech extension URI to VS Code")


def _close_vscode_tab(token: str) -> None:
    _open_vscode_uri(
        "vscode://rti.medtech-web-tabs/close-owned?"
        + urllib.parse.urlencode({"closeToken": token})
    )


def _close_vscode_tabs() -> None:
    _open_vscode_uri("vscode://rti.medtech-web-tabs/close")


def _open_when_ready(url: str, title: str, token: str, stopped: threading.Event) -> None:
    deadline = time.monotonic() + 30
    while not stopped.is_set() and time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url + "api/state", timeout=1) as response:
                ready = response.status == 200
        except (OSError, urllib.error.URLError):
            ready = False
        if ready:
            if not stopped.is_set():
                query = urllib.parse.urlencode({"url": url, "title": title, "closeToken": token})
                _open_vscode_uri(f"vscode://rti.medtech-web-tabs/open?{query}")
            return
        stopped.wait(0.25)
    if not stopped.is_set():
        print(f"Web UI did not become ready: {url}", file=sys.stderr)


def _watch_tab_closures(
    children, close_tokens, stopped, state_dir=None, sensor_index=None, closed=None,
) -> None:
    state_dir = state_dir or _tab_state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)
    pending = dict(close_tokens)
    sensor = children[sensor_index] if sensor_index is not None else None
    sensor_record = state_dir / "PatientSensor.process"

    def record_sensor(pid):
        if pid is None and json.loads(sensor_record.read_text()).get("pid") != children[sensor_index].pid:
            return
        temporary = sensor_record.with_suffix(f".{uuid.uuid4().hex}.tmp")
        temporary.write_text(json.dumps({"pid": pid}))
        temporary.replace(sensor_record)

    if sensor is not None:
        record_sensor(sensor.pid)
    while (pending or sensor is not None) and not stopped.is_set():
        if sensor is not None and sensor.poll() is not None:
            record_sensor(None)
            sensor = None
        for index, token in list(pending.items()):
            request = state_dir / f"{token}.close"
            child = children[index]
            if request.exists():
                if closed is not None:
                    closed.add(index)
                if child.poll() is None:
                    try:
                        child.kill()
                    except ProcessLookupError:
                        pass
                request.unlink(missing_ok=True)
                del pending[index]
            elif child.poll() is not None:
                _close_vscode_tab(token)
                del pending[index]
        stopped.wait(0.1)
    if sensor is not None and sensor.poll() is not None:
        record_sensor(None)


def _shutdown(children) -> None:
    errors = []
    for child in children:
        try:
            if child.poll() is None:
                child.terminate()
        except ProcessLookupError:
            pass
        except BaseException as error:
            errors.append(error)
    deadline = time.monotonic() + 1
    for child in children:
        try:
            child.wait(timeout=max(0, deadline - time.monotonic()))
            continue
        except subprocess.TimeoutExpired:
            pass
        except BaseException as error:
            errors.append(error)
        try:
            child.kill()
        except ProcessLookupError:
            pass
        except BaseException as error:
            errors.append(error)
        try:
            child.wait(timeout=1)
        except BaseException as error:
            errors.append(error)
    if errors:
        raise errors[0]


def _interrupt_launch(_signum, _frame):
    raise KeyboardInterrupt


def _launch(commands, module_dir, env, *, web_urls, keep_alive=False) -> None:
    children = []
    tokens = {}
    stopped = threading.Event()
    closed = set()
    workers = []
    previous_handler = signal.signal(signal.SIGTERM, _interrupt_launch)
    try:
        for command in commands:
            children.append(subprocess.Popen(command, cwd=module_dir, env=env))
        sensor_index = next(
            (index for index, command in enumerate(commands)
             if Path(command[0]).name == "PatientSensor"), None,
        )
        for index, title, url in web_urls:
            token = uuid.uuid4().hex
            tokens[index] = token
            workers.append(threading.Thread(
                target=_open_when_ready, args=(url, title, token, stopped), daemon=True,
            ))
        workers.append(threading.Thread(
            target=_watch_tab_closures,
            args=(children, tokens, stopped, None, sensor_index, closed), daemon=True,
        ))
        for worker in workers:
            worker.start()
        running = set(range(len(children)))
        while running or keep_alive:
            for index in tuple(running):
                child = children[index]
                code = child.poll()
                if code is None:
                    continue
                running.remove(index)
                if code != 0 and index not in closed:
                    print(
                        f"Application exited with code {code}: {child.args}",
                        file=sys.stderr, flush=True,
                    )
            if running or keep_alive:
                time.sleep(0.1)
    finally:
        original_error = sys.exc_info()[1]
        try:
            _shutdown(children)
        except BaseException as cleanup_error:
            if original_error is None:
                raise
            print(f"Child cleanup also failed: {cleanup_error!r}", file=sys.stderr)
        finally:
            stopped.set()
            for worker in workers:
                if worker.ident is not None:
                    worker.join()
            signal.signal(signal.SIGTERM, previous_handler)
            if keep_alive:
                _close_vscode_tabs()
            else:
                for token in tokens.values():
                    _close_vscode_tab(token)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apps", nargs="*", help="Device names; defaults to the complete operating room")
    parser.add_argument("-s", "--security", action="store_true")
    args = parser.parse_args()

    sys.path.insert(0, str(PROJECT_ROOT))
    import launch as reference

    try:
        commands, module_dir, env = reference._resolve_module(
            "01-operating-room", args.apps or None, args.security,
        )
    except ValueError as error:
        parser.error(str(error))
    web_urls = [
        (index, title, url)
        for index, command in enumerate(commands)
        for title, url in reference._web_urls([([command], module_dir, env)])
    ]
    if not args.apps:
        _open_vscode_uri(f"vscode://rti.medtech-web-tabs/session?secure={int(args.security)}")
    try:
        _launch(commands, module_dir, env, web_urls=web_urls, keep_alive=not args.apps)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
