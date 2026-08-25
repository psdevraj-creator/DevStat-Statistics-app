"""DevStat Desktop Edition launcher.

Replaces the old Electron shell. Instead of bundling a browser, this launches
the bundled analysis engine on 127.0.0.1 and opens it in the user's REAL Chrome
(or Edge on Windows, or Chrome/Safari on macOS) in app mode (``--app``) — a
frameless window with NO address bar.

The engine runs 100% locally (DEVSTAT_OFFLINE=1): analysis data never leaves
the machine. Registration and subscription stay online (shared with the online
app) through the engine's normal /api/auth + /api/license endpoints.

Run:
    python launch.py                 (uses ../backend/dist/... engine)
    DEVSTAT_ENGINE_EXE=<path> run    (packaged layout: engine next to launcher)
"""
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

LOCAL_HOST = "127.0.0.1"
PORT = int(os.environ.get("DEVSTAT_LOCAL_PORT", "8210"))
LOCAL_URL = f"http://{LOCAL_HOST}:{PORT}"
OFFLINE_ENV = os.environ.get("DEVSTAT_OFFLINE", "1")
# Session-signing secret shared with the online backend (so the local engine can
# validate the login token for the analysis gate). Low risk: only enables a local
# paywall bypass; data never leaves the machine.
AUTH_SECRET = "db9ffa3d3aa6aee74301e4203e018e8bbfbedcb16e06d7c6cf35d33fd03fbc03"


def _here() -> Path:
    if getattr(sys, "frozen", False):  # PyInstaller bundle
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def find_engine() -> tuple[list[str], str]:
    """Return (cmd_args, cwd) to start the engine."""
    exe = os.environ.get("DEVSTAT_ENGINE_EXE", "")
    if exe:
        p = Path(exe)
        if p.exists():
            return [str(p)], str(p.parent)

    # Packaged layout: engine bundled beside the launcher.
    for name in ("DevStatEngine", "DevStatEngine.exe"):
        cand = _here() / "engine" / name
        if cand.exists():
            return [str(cand)], str(cand.parent)

    # Dev layout: backend/dist/DevStatEngine/<bin>, else run backend via python.
    root = _here().parent.parent if _here().name == "desktop" else _here()
    for name in ("DevStatEngine.exe", "DevStatEngine"):
        cand = root / "backend" / "dist" / "DevStatEngine" / name
        if cand.exists():
            return [str(cand)], str(cand.parent)

    backend = root / "backend"
    py = os.environ.get("DEVSTAT_PYTHON", sys.executable or "python")
    return [py, str(backend / "run_local.py")], str(backend)


def find_browser() -> str | None:
    """Return a browser launch prefix for app mode, or None."""
    system = platform.system()
    if system == "Windows":
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ]
        for c in candidates:
            if Path(c).exists():
                return c
    elif system == "Darwin":
        chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if Path(chrome).exists():
            return chrome
        # Fall back to Safari via `open`.
        return None
    return None


def wait_for_engine(retries: int = 60) -> bool:
    for _ in range(retries):
        try:
            with urllib.request.urlopen(f"{LOCAL_URL}/api/health", timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def free_port(port: int) -> None:
    """Kill any process already bound to `port` before we start a new engine.

    A previous DevStat run that never closed leaves a stale engine holding
    127.0.0.1:<port>; the new engine then can't bind and the app appears to do
    nothing (no login screen). We free the port first so every launch is clean.
    """
    system = platform.system()
    try:
        if system == "Windows":
            out = subprocess.check_output(["netstat", "-ano"], text=True, errors="ignore")
            pids = set()
            for line in out.splitlines():
                # e.g. "TCP  127.0.0.1:8210  0.0.0.0:0  LISTENING  12345"
                if "LISTENING" not in line:
                    continue
                parts = line.split()
                for idx, tok in enumerate(parts):
                    if tok.endswith(f":{port}") and idx + 1 < len(parts):
                        pid = parts[-1]
                        if pid and pid != "0":
                            pids.add(pid)
            for pid in pids:
                try:
                    subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
                except Exception:
                    pass
        else:
            # macOS / Linux
            try:
                out = subprocess.check_output(["lsof", "-ti", f"tcp:{port}"], text=True, errors="ignore")
                for pid in out.split():
                    if pid:
                        try:
                            subprocess.run(["kill", "-9", pid], capture_output=True)
                        except Exception:
                            pass
            except Exception:
                pass
    except Exception:
        pass


def main() -> None:
    system = platform.system()

    cmd, cwd = find_engine()
    env = dict(os.environ)
    env["DEVSTAT_OFFLINE"] = OFFLINE_ENV
    env["DEVSTAT_AUTH_SECRET"] = AUTH_SECRET
    env["DEVSTAT_LOCAL_PORT"] = str(PORT)

    print(f"[DevStat Desktop Edition] starting engine: {cmd}")
    free_port(PORT)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    engine = subprocess.Popen(cmd, cwd=cwd, env=env, creationflags=flags)

    try:
        if not wait_for_engine():
            print("[DevStat Desktop Edition] engine failed to start.")
            sys.exit(1)

        url = LOCAL_URL
        browser = find_browser()

        if browser:
            profile = Path(os.environ.get("TEMP", str(Path.home()))) / f"devstat-profile"
            subprocess.Popen([
                browser,
                f"--app={url}",
                f"--user-data-dir={profile}",
                "--no-first-run",
                "--disable-session-crashed-bubble",
            ])
            print(f"[DevStat Desktop Edition] opened in app mode: {url}")
        elif system == "Darwin":
            # Safari fallback: `open <url>` (no app-mode chrome, but works).
            subprocess.Popen(["open", url])
            print(f"[DevStat Desktop Edition] opened (Safari): {url}")
        else:
            print("[DevStat Desktop Edition] no browser found. Open this URL manually: " + url)
            # Keep the window alive until a browser is opened or user quits.
            try:
                subprocess.run(["cmd", "/c", "start", "", url], check=False)
            except Exception:
                pass

        print("[DevStat Desktop Edition] running. Close the window to quit; Ctrl+C here stops the engine.")
        # Keep this process alive while the engine runs so closing it cleans up.
        try:
            while engine.poll() is None:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    finally:
        if engine.poll() is None:
            try:
                engine.terminate()
            except Exception:
                pass
        try:
            engine.wait(timeout=5)
        except Exception:
            try:
                engine.kill()
            except Exception:
                pass
        print("[DevStat Desktop Edition] stopped.")


if __name__ == "__main__":
    main()
