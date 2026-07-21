"""
DevStat Launcher — simple start/stop window for the DevStat medical statistics app.
Spawns a hidden --server subprocess (PyInstaller-compatible).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk
from pathlib import Path
import urllib.request
import webbrowser

if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(sys._MEIPASS)
else:
    PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"
BACKEND_PORT = "8150"
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"


def _get_chrome():
    import shutil
    for exe in ["chrome", "msedge", "brave", "chromium"]:
        path = shutil.which(exe) or shutil.which(f"{exe}.exe")
        if path:
            return path
    prog = os.environ.get("ProgramFiles", "C:\\Program Files")
    for pfx in ["Google\\Chrome\\Application", "Microsoft\\Edge\\Application"]:
        p = Path(prog) / pfx / "chrome.exe"
        if p.exists():
            return str(p)
    return None


def run_server():
    """Start uvicorn server in the current process (--server mode)."""
    try:
        if getattr(sys, 'frozen', False):
            root = Path(sys._MEIPASS)
        else:
            root = Path(__file__).resolve().parent
        backend = root / "backend"
        os.chdir(str(backend))
        sys.path.insert(0, str(backend))
        import uvicorn
        uvicorn.run(
            "app.main:create_app",
            host="127.0.0.1",
            port=int(BACKEND_PORT),
            factory=True,
            log_level="warning",
        )
    except Exception:
        import traceback
        crash_log = (Path(__file__).resolve().parent if not getattr(sys, 'frozen', False) else Path(sys._MEIPASS).parent) / "devstat_crash.log"
        try:
            with open(str(crash_log), "w") as f:
                f.write(traceback.format_exc())
        except Exception:
            pass
        raise


class DevStatLauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("DevStat")
        self.root.geometry("520x340")
        self.root.resizable(False, False)
        self.root.configure(bg="#ffffff")

        self._server_proc = None
        self.browser_proc = None
        self.backend_ready = False
        self.monitor_active = True
        self._stopping = False

        self._build_ui()
        self._start_monitor()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _build_ui(self):
        header = tk.Frame(self.root, bg="#005eb8", height=80)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        accent = tk.Frame(header, bg="#4db8ff", height=3)
        accent.pack(fill=tk.X, side=tk.BOTTOM)
        logo_frame = tk.Frame(header, bg="#005eb8")
        logo_frame.pack(side=tk.LEFT, padx=(24, 0), pady=12)
        icon_canvas = tk.Canvas(logo_frame, width=42, height=42, bg="#005eb8", highlightthickness=0)
        icon_canvas.create_oval(0, 0, 42, 42, fill="#ffffff", outline="")
        icon_canvas.create_text(21, 21, text="D", font=("Segoe UI", 20, "bold"), fill="#005eb8")
        icon_canvas.pack(side=tk.LEFT, padx=(0, 14))
        title_frame = tk.Frame(logo_frame, bg="#005eb8")
        title_frame.pack(side=tk.LEFT)
        tk.Label(title_frame, text="DevStat", font=("Segoe UI", 20, "bold"),
                 fg="#ffffff", bg="#005eb8").pack(anchor="w")
        tk.Label(title_frame, text="Medical Statistics", font=("Segoe UI", 9),
                 fg="#b3d9ff", bg="#005eb8").pack(anchor="w")
        self.badge = tk.Label(header, text="● Stopped", font=("Segoe UI", 9, "bold"),
                              fg="#ff6b6b", bg="#005eb8")
        self.badge.pack(side=tk.RIGHT, padx=(0, 24), pady=30)

        main = tk.Frame(self.root, bg="#ffffff", padx=32, pady=24)
        main.pack(fill=tk.BOTH, expand=True)
        self.status_label = tk.Label(main, text="Press Start to launch the application",
                                     font=("Segoe UI", 11), fg="#888888", bg="#ffffff")
        self.status_label.pack(pady=(8, 20))

        btn_frame = tk.Frame(main, bg="#ffffff")
        btn_frame.pack()
        btn_style = {"font": ("Segoe UI", 10, "bold"), "width": 14, "height": 1,
                     "relief": "flat", "cursor": "hand2", "bd": 0}
        self.start_btn = tk.Button(btn_frame, text="▶  Start", command=self._start_backend,
                                   bg="#005eb8", fg="#ffffff", activebackground="#004a94",
                                   activeforeground="#ffffff", **btn_style)
        self.start_btn.pack(side=tk.LEFT, padx=5, ipady=6)
        self.stop_btn = tk.Button(btn_frame, text="■  Stop", command=self._stop_backend,
                                  bg="#e53e3e", fg="#ffffff", activebackground="#c53030",
                                  activeforeground="#ffffff", state=tk.DISABLED, **btn_style)
        self.stop_btn.pack(side=tk.LEFT, padx=5, ipady=6)
        self.open_btn = tk.Button(btn_frame, text="🌐  Open App", command=self._open_browser,
                                  bg="#38a169", fg="#ffffff", activebackground="#2f855a",
                                  activeforeground="#ffffff", state=tk.DISABLED, **btn_style)
        self.open_btn.pack(side=tk.LEFT, padx=5, ipady=6)

        bar_bg = "#edf2f7"
        self.status_bar = tk.Label(self.root, text="", font=("Segoe UI", 9),
                                   fg="#4a5568", bg=bar_bg, anchor="w", padx=16, pady=6)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        sep = tk.Frame(self.root, bg="#e2e8f0", height=1)
        sep.pack(fill=tk.X, side=tk.BOTTOM)

    # ── Server management ──────────────────────────────────────────────

    def _start_backend(self):
        if self._server_proc and self._server_proc.poll() is None:
            return
        # Kill any stale process on our port (leftover from a previous crash)
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                port_busy = s.connect_ex(('127.0.0.1', int(BACKEND_PORT))) == 0
            if port_busy:
                self.status_bar.configure(text="Port in use — terminating old process...")
                cmd = f'netstat -ano | findstr "127.0.0.1:{BACKEND_PORT}" | findstr "LISTENING"'
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
                for line in result.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 5:
                        subprocess.run(f'taskkill /f /pid {parts[4]}', shell=True, capture_output=True)
                time.sleep(1)
        except Exception:
            pass
        self._set_controls(start=False, stop=True, open_=False)
        self.badge.configure(text="● Starting", fg="#ecc94b")
        self.status_label.configure(text="Starting server...", fg="#e0a800")
        self.status_bar.configure(text="Launching backend")
        self.backend_ready = False

        if getattr(sys, 'frozen', False):
            cmd = [sys.executable, "--server"]
        else:
            cmd = [sys.executable, str(Path(__file__).resolve()), "--server"]
        self._server_proc = subprocess.Popen(
            cmd,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def _stop_backend(self):
        self._stopping = True
        if self._server_proc and self._server_proc.poll() is None:
            try:
                self._server_proc.terminate()
                self._server_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._server_proc.kill()
                self._server_proc.wait()
        self._server_proc = None
        self.backend_ready = False

        if self.browser_proc and self.browser_proc.poll() is None:
            try:
                self.browser_proc.terminate()
            except Exception:
                pass
            self.browser_proc = None
        self._on_stopped()
        self._stopping = False

    def _open_browser(self):
        chrome = _get_chrome()
        if chrome:
            self.browser_proc = subprocess.Popen(
                [chrome, f"--app={BACKEND_URL}", "--new-window"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            webbrowser.open(BACKEND_URL)

    def _set_controls(self, start, stop, open_):
        self.start_btn.configure(state=tk.NORMAL if start else tk.DISABLED,
                                 bg="#005eb8" if start else "#a0aec0")
        self.stop_btn.configure(state=tk.NORMAL if stop else tk.DISABLED,
                                bg="#e53e3e" if stop else "#a0aec0")
        self.open_btn.configure(state=tk.NORMAL if open_ else tk.DISABLED,
                                bg="#38a169" if open_ else "#a0aec0")

    # ── Health monitoring ──────────────────────────────────────────────

    def _start_monitor(self):
        def _poll():
            startup_phase = True
            poll_count = 0
            while self.monitor_active:
                try:
                    resp = urllib.request.urlopen(f"{BACKEND_URL}/api/health", timeout=2)
                    if resp.status == 200:
                        if not self.backend_ready:
                            self.root.after(0, self._on_ready)
                        startup_phase = False
                    else:
                        if self.backend_ready:
                            self.root.after(0, self._on_crash)
                except Exception:
                    if self.backend_ready:
                        self.root.after(0, self._on_crash)
                    elif startup_phase:
                        poll_count += 1
                        if poll_count == 3:
                            self.root.after(0, lambda: self.status_bar.configure(text="Starting — loading modules..."))
                        elif poll_count == 8:
                            self.root.after(0, lambda: self.status_bar.configure(text="Still starting — large module import..."))
                        elif poll_count == 15:
                            self.root.after(0, lambda: self.status_bar.configure(text="Starting — almost ready..."))
                time.sleep(1)

        threading.Thread(target=_poll, daemon=True).start()

    def _on_ready(self):
        if self._stopping:
            return
        self.backend_ready = True
        self._set_controls(start=False, stop=True, open_=True)
        self.badge.configure(text="● Running", fg="#4ec9b0")
        self.status_label.configure(text="Ready — open the app in your browser", fg="#38a169")
        self.status_bar.configure(text=BACKEND_URL)

    def _on_stopped(self):
        self._set_controls(start=True, stop=False, open_=False)
        self.badge.configure(text="● Stopped", fg="#ff6b6b")
        self.status_label.configure(text="Stopped", fg="#888888")
        self.status_bar.configure(text="")

    def _on_crash(self):
        self.backend_ready = False
        self._set_controls(start=True, stop=False, open_=False)
        self.badge.configure(text="● Crashed", fg="#f44747")
        self.status_label.configure(text="Server stopped unexpectedly", fg="#f44747")
        self.status_bar.configure(text="Click Start to restart")

    # ── Cleanup ────────────────────────────────────────────────────────

    def _on_close(self):
        self.monitor_active = False
        self._stop_backend()
        self.root.destroy()


if __name__ == "__main__":
    if "--server" in sys.argv:
        run_server()
    else:
        DevStatLauncher()
