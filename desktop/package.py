"""Package the DevStat Desktop Edition for distribution.

Assembles the PyInstaller-built engine + launcher into a distributable folder
and zips it. On macOS it also builds a proper .app bundle so double-clicking
works (no terminal needed).

Usage:
  python package.py --os win   --engine-dir <...> --launcher <...> --out <dir>
  python package.py --os mac   --engine-dir <...> --launcher <...> --out <dir>
"""
import argparse
import shutil
import zipfile
from pathlib import Path

APP_NAME = "DevStat Desktop Edition"


def assemble(out: Path, engine_dir: Path, launcher: Path, os_name: str) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    app = out / APP_NAME
    if app.exists():
        shutil.rmtree(app)

    if os_name == "mac":
        # Build a minimal .app bundle at the top level.
        bundle = out / f"{APP_NAME}.app"
        macos = bundle / "Contents" / "MacOS"
        res = bundle / "Contents" / "Resources"
        macos.mkdir(parents=True, exist_ok=True)
        res.mkdir(parents=True, exist_ok=True)
        bin_name = launcher.name or "DevStatDesktopLauncher"
        shutil.copy(launcher, macos / bin_name)

        # Info.plist
        plist = bundle / "Contents" / "Info.plist"
        plist.write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>DevStat</string>
<key>CFBundleDisplayName</key><string>{APP_NAME}</string>
<key>CFBundleIdentifier</key><string>com.devstat.app</string>
<key>CFBundleVersion</key><string>1.0</string>
<key>CFBundleShortVersionString</key><string>1.0</string>
<key>CFBundleExecutable</key><string>{bin_name}</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>NSHighResolutionCapable</key><true/>
</dict></plist>
""",
            encoding="utf-8",
        )
        # Engine is looked up relative to the launcher; place at engine/.
        shutil.copytree(engine_dir, bundle / "Contents" / "Resources" / "engine")
    else:
        app.mkdir(parents=True, exist_ok=True)
        shutil.copy2(launcher, app / (launcher.name or "DevStatDesktopLauncher.exe"))
        shutil.copytree(engine_dir, app / "engine")

        # A convenience start script (the launcher exe is the real entry point).
        (app / "START-HERE.txt").write_text(
            "DevStat Desktop Edition\n=======================\n"
            "Double-click  DevStatDesktopLauncher.exe  to launch DevStat in your browser "
            "(Chrome/Edge app window, no address bar).\n\n"
            "Your analysis data never leaves this machine.\n",
            encoding="utf-8",
        )

    # Zip it up.
    base = out / APP_NAME
    zip_path = out / f"DevStat-Desktop-{os_name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(base.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(out))
    return zip_path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--os", choices=["win", "mac"], required=True)
    p.add_argument("--engine-dir", required=True)
    p.add_argument("--launcher", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()

    engine_dir = Path(a.engine_dir)
    launcher = Path(a.launcher)
    if not engine_dir.exists() or not launcher.exists():
        raise SystemExit(f"Missing engine-dir or launcher: {engine_dir} / {launcher}")

    zip_path = assemble(Path(a.out), engine_dir, launcher, a.os)
    print(f"PACKED: {zip_path}")


if __name__ == "__main__":
    main()
