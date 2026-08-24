"""DevStat local (offline) server launcher.

Runs the full analysis engine on 127.0.0.1 with NO external dependencies
(no Cloud Run, no Firebase, no Stripe required to compute). Data stays on the
machine. Used by the desktop/offline build.

Licensing for the offline build is handled by the Electron shell (see
frontend/electron/main.js + licence.js): it talks to the hosted backend for
licence status and caches a signed token locally. This server only computes.
"""
import os
import sys
from pathlib import Path

# backend/ must be the ONLY directory on the path so the `app` package resolves
# to exactly one module (a duplicate import would give analysis a second,
# empty in-memory state).
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("PYTHONPATH", str(BACKEND_DIR))

# Load backend/.env if present (dev convenience); harmless if absent.
from app import config  # noqa: F401  (importing triggers _load_dotenv)

import uvicorn  # noqa: E402


def main() -> None:
    port = int(os.environ.get("DEVSTAT_LOCAL_PORT", "8210"))
    uvicorn.run(
        "app.main:create_app",
        host="127.0.0.1",
        port=port,
        factory=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
