"""
DevStat Launcher — simple start/stop window for the DevStat medical statistics app.
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

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"
BACKEND_PORT = "8150"
PYTHON_CMD = [sys.executable]


def _get_chrome():
    """Find Chrome/Edge/Brave executable path."""
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


class DevStatLauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("DevStat")
        self.root.geometry("520x340")
        self.root.resizable(False, False)
        self.root.configure(bg="#ffffff")

        self.backend_proc: subprocess.Popen | None = None
        self.browser_proc: subprocess.Popen | None = None
        self.backend_ready = False
        self.monitor_active = True

        self._build_ui()
        self._start_monitor()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _build_ui(self):
        # ── Header bar ──
        header = tk.Frame(self.root, bg="#005eb8", height=80)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        # Accent line
        accent = tk.Frame(header, bg="#4db8ff", height=3)
        accent.pack(fill=tk.X, side=tk.BOTTOM)

        # Logo area
        logo_frame = tk.Frame(header, bg="#005eb8")
        logo_frame.pack(side=tk.LEFT, padx=(24, 0), pady=12)

        # Icon circle with D
        icon_canvas = tk.Canvas(logo_frame, width=42, height=42, bg="#005eb8", highlightthickness=0)
        icon_canvas.create_oval(0, 0, 42, 42, fill="#ffffff", outline="")
        icon_canvas.create_text(21, 21, text="D", font=("Segoe UI", 20, "bold"), fill="#005eb8")
        icon_canvas.pack(side=tk.LEFT, padx=(0, 14))

        # Title + subtitle
        title_frame = tk.Frame(logo_frame, bg="#005eb8")
        title_frame.pack(side=tk.LEFT)
        tk.Label(title_frame, text="DevStat", font=("Segoe UI", 20, "bold"),
                 fg="#ffffff", bg="#005eb8").pack(anchor="w")
        tk.Label(title_frame, text="Medical Statistics", font=("Segoe UI", 9),
                 fg="#b3d9ff", bg="#005eb8").pack(anchor="w")

        # Status badge (top-right)
        self.badge = tk.Label(header, text="● Stopped", font=("Segoe UI", 9, "bold"),
                              fg="#ff6b6b", bg="#005eb8")
        self.badge.pack(side=tk.RIGHT, padx=(0, 24), pady=30)

        # ── Main content ──
        main = tk.Frame(self.root, bg="#ffffff", padx=32, pady=24)
        main.pack(fill=tk.BOTH, expand=True)

        # Status message
        self.status_label = tk.Label(main, text="Press Start to launch the application",
                                     font=("Segoe UI", 11), fg="#888888", bg="#ffffff")
        self.status_label.pack(pady=(8, 20))

        # ── Buttons ──
        btn_frame = tk.Frame(main, bg="#ffffff")
        btn_frame.pack(pady=(0, 0))

        btn_style = {"font": ("Segoe UI", 10, "bold"), "width": 14, "height": 1,
                     "relief": "flat", "cursor": "hand2", "bd": 0}

        self.start_btn = tk.Button(btn_frame, text="▶  Start", command=self._start_all,
                                   bg="#005eb8", fg="#ffffff", activebackground="#004a94",
                                   activeforeground="#ffffff", **btn_style)
        self.start_btn.pack(side=tk.LEFT, padx=5, ipady=6)

        self.stop_btn = tk.Button(btn_frame, text="■  Stop", command=self._stop_all,
                                  bg="#e53e3e", fg="#ffffff", activebackground="#c53030",
                                  activeforeground="#ffffff", state=tk.DISABLED, **btn_style)
        self.stop_btn.pack(side=tk.LEFT, padx=5, ipady=6)

        self.open_btn = tk.Button(btn_frame, text="🌐  Open App", command=self._open_browser,
                                  bg="#38a169", fg="#ffffff", activebackground="#2f855a",
                                  activeforeground="#ffffff", state=tk.DISABLED, **btn_style)
        self.open_btn.pack(side=tk.LEFT, padx=5, ipady=6)

        # ── Status bar (bottom) ──
        bar_bg = "#edf2f7"
        self.status_bar = tk.Label(self.root, text="", font=("Segoe UI", 9),
                                   fg="#4a5568", bg=bar_bg, anchor="w", padx=16, pady=6)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        # Separator line above status bar
        sep = tk.Frame(self.root, bg="#e2e8f0", height=1)
        sep.pack(fill=tk.X, side=tk.BOTTOM)

    # ── Process management ─────────────────────────────────────────────

    def _start_all(self):
        self._stop_all()
        self.start_btn.configure(state=tk.DISABLED, bg="#a0aec0")
        self.stop_btn.configure(state=tk.NORMAL, bg="#e53e3e")
        self.open_btn.configure(state=tk.DISABLED, bg="#a0aec0")
        self.status_label.configure(text="Starting server...", fg="#e0a800")
        self.badge.configure(text="● Starting", fg="#ecc94b")
        self.status_bar.configure(text="Launching backend...")
        self.backend_ready = False

        self.backend_proc = subprocess.Popen(
            [*PYTHON_CMD, "-m", "uvicorn", "app.main:create_app",
             "--host", "127.0.0.1", "--port", BACKEND_PORT, "--factory"],
            cwd=str(BACKEND_DIR),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        threading.Thread(target=self._read_backend, daemon=True).start()

    def _stop_all(self):
        self.monitor_active = False
        self.backend_ready = False

        if self.backend_proc and self.backend_proc.poll() is None:
            try:
                self.backend_proc.terminate()
                self.backend_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.backend_proc.kill()
                self.backend_proc.wait()

        if self.browser_proc and self.browser_proc.poll() is None:
            try:
                self.browser_proc.terminate()
                self.browser_proc.wait(timeout=3)
            except Exception:
                self.browser_proc.kill()

        subprocess.run(
            f'for /f "tokens=5" %p in (\'netstat -ano ^| findstr "127.0.0.1:{BACKEND_PORT} "'
            f' ^| findstr "LISTENING"\') do taskkill /f /pid %p >nul 2>&1',
            shell=True, capture_output=True,
        )

        self.backend_proc = None
        self.browser_proc = None
        self.start_btn.configure(state=tk.NORMAL, bg="#005eb8")
        self.stop_btn.configure(state=tk.DISABLED, bg="#a0aec0")
        self.open_btn.configure(state=tk.DISABLED, bg="#a0aec0")
        self.status_label.configure(text="Stopped", fg="#888888")
        self.badge.configure(text="● Stopped", fg="#ff6b6b")
        self.status_bar.configure(text="")
        self.monitor_active = True

    def _open_browser(self):
        chrome = _get_chrome()
        if chrome:
            self.browser_proc = subprocess.Popen(
                [chrome, f"--app=http://127.0.0.1:{BACKEND_PORT}", "--new-window"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            import webbrowser
            webbrowser.open(f"http://127.0.0.1:{BACKEND_PORT}")

    # ── Process reader ─────────────────────────────────────────────────

    def _read_backend(self):
        try:
            for line in iter(self.backend_proc.stdout.readline, ""):
                if not self.monitor_active:
                    break
                if "Uvicorn running on" in line or "Application startup complete" in line:
                    self.root.after(0, self._on_ready)
        except Exception:
            pass

    def _on_ready(self):
        self.backend_ready = True
        self.start_btn.configure(state=tk.DISABLED, bg="#a0aec0")
        self.stop_btn.configure(state=tk.NORMAL, bg="#e53e3e")
        self.open_btn.configure(state=tk.NORMAL, bg="#38a169")
        self.status_label.configure(text="Ready — open the app in your browser", fg="#38a169")
        self.badge.configure(text="● Running", fg="#4ec9b0")
        self.status_bar.configure(text="http://localhost:8150")

    # ── Health monitor ─────────────────────────────────────────────────

    def _start_monitor(self):
        def _poll():
            while self.monitor_active:
                try:
                    import urllib.request
                    resp = urllib.request.urlopen(
                        f"http://127.0.0.1:{BACKEND_PORT}/api/health", timeout=2
                    )
                    if resp.status == 200 and not self.backend_ready:
                        self.root.after(0, self._on_ready)
                except Exception:
                    if self.backend_ready:
                        self.root.after(0, self._on_crash)
                time.sleep(5)

        threading.Thread(target=_poll, daemon=True).start()

    def _on_crash(self):
        self.backend_ready = False
        self.start_btn.configure(state=tk.NORMAL, bg="#005eb8")
        self.stop_btn.configure(state=tk.DISABLED, bg="#a0aec0")
        self.open_btn.configure(state=tk.DISABLED, bg="#a0aec0")
        self.status_label.configure(text="Server stopped unexpectedly", fg="#f44747")
        self.badge.configure(text="● Crashed", fg="#f44747")
        self.status_bar.configure(text="Click Start to restart")

    # ── Cleanup ────────────────────────────────────────────────────────

    def _on_close(self):
        self.monitor_active = False
        if self.backend_proc:
            try:
                self.backend_proc.terminate()
                self.backend_proc.wait(timeout=3)
            except Exception:
                pass
        if self.browser_proc and self.browser_proc.poll() is None:
            try:
                self.browser_proc.terminate()
            except Exception:
                pass
        self.root.destroy()


if __name__ == "__main__":
    DevStatLauncher()
