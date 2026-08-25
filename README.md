# DevStat — Medical Statistics Software

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://github.com/psdevraj-creator/DevStat-Statistics-app/codespaces)
[![User Guide](https://img.shields.io/badge/%F0%9F%93%96-User_Guide_%26_Statistics_Manual-005eb8?style=for-the-badge)](https://dpsoncology.com/STATS_MANUAL.html)

> **Try it instantly in your browser** — click the Codespaces badge above. No installation, no setup.

A medical statistics application for statistical analysis and visualisation of clinical data.

## Quick Start (Codespaces)

1. Click the **Open in GitHub Codespaces** badge above
2. Wait ~2 minutes for setup to complete
3. Run `bash codespace_setup/start.sh` in the terminal
4. Open the forwarded port 8150 in your browser

## Quick Start (Desktop)

Download the latest release from the [Releases page](https://github.com/psdevraj-creator/DevStat-Statistics-app/releases).

## Development

```bash
pip install -r requirements.txt
cd backend && uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8150
```

See [SETUP.md](SETUP.md) for full instructions.

## What's New in v1.2

- **Faster loading** — pages now load only when you click them, so the app starts quicker
- **Undo and redo buttons** — visible in the top toolbar at all times
- **Better error messages** — if something goes wrong (e.g. loading data), a yellow message appears instead of a blank screen
- **Cleaner output viewer** — the Results page is more reliable and shows a helpful message when empty
- **No more hardcoded Python version** — the launcher detects whatever Python you have installed
- **Fixed: data never silently fails** — errors loading datasets or columns now show a warning instead of being hidden
- **Fixed: dead code removed** — old debug messages and unused chart types cleaned up
- **Privacy improvement** — request logging no longer captures data content unless you specifically enable it with `DEVSTAT_LOG_BODY=true`
- **Missing packages added** — `chardet`, `factor-analyzer`, `pingouin`, and `weasyprint` are now listed in `requirements.txt` and installed automatically

## Desktop Edition (fully offline)

The **Desktop Edition** runs the whole analysis engine on your own machine:

- **Data never leaves your computer** — every statistic computed locally. Nothing is uploaded for analysis.
- **Opens in your own browser, app-style** (Chrome/Edge on Windows, Chrome/Safari on macOS) with no address bar — no Electron, no extra runtime.
- **Register & subscribe online** — sign in / register / upgrade through the normal DevStat account (the same login works on the online app). Only account data goes online; your analysis stays local.
- **Free 5 analyses + 5 charts**, then a **£25/year licence** for unlimited use.

**Download:** grab the zip for your OS from the [Releases](https://github.com/psdevraj-creator/DevStat-Statistics-app/releases) page — extract, then double-click **DevStatDesktopLauncher** (Windows) or **DevStat Desktop Edition.app** (macOS).
