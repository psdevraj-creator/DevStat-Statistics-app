"""
End-to-end integration test for the AI Assistant module.

Starts DevStat server fresh, uploads sample data, tests all AI endpoints,
then reports results. Uses subprocess for clean server isolation.
"""
import os
import sys
import time
import json
import signal
import subprocess
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
SAMPLE_CSV = PROJECT_DIR / "sample_100.csv"
PORT = 8150
BASE_URL = f"http://127.0.0.1:{PORT}"

PASS = 0
FAIL = 0
ERRORS = []


def report(name, status, detail=""):
    global PASS, FAIL
    if status:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}: {detail}")
        ERRORS.append(f"{name}: {detail}")


def wait_for_server(url, timeout=30):
    import requests
    for i in range(timeout):
        try:
            r = requests.get(f"{url}/api/health", timeout=2)
            if r.status_code == 200:
                return True
        except requests.ConnectionError:
            pass
        time.sleep(1)
    return False


def clear_pycache():
    """Remove all __pycache__ directories under backend."""
    count = 0
    for p in BACKEND_DIR.rglob("__pycache__"):
        if p.is_dir():
            import shutil
            shutil.rmtree(p, ignore_errors=True)
            count += 1
    # Also remove .pyc files
    for p in BACKEND_DIR.rglob("*.pyc"):
        try:
            p.unlink()
        except OSError:
            pass
    return count


def main():
    global PASS, FAIL, ERRORS

    print("=" * 65)
    print("  DEVSTAT AI — END-TO-END INTEGRATION TEST")
    print("=" * 65)
    print()

    # 1. Clear Python cache
    print("[1/8] Clearing Python cache...")
    n = clear_pycache()
    print(f"       Removed {n} cache directories")

    # 2. Kill any existing DevStat server
    print("[2/8] Stopping existing DevStat servers...")
    if sys.platform == "win32":
        subprocess.run(
            "wmic path win32_process where \"commandline like '%uvicorn%' and "
            "not name like '%wmic%'\" call terminate 2>nul",
            shell=True, capture_output=True,
        )
    else:
        subprocess.run(["pkill", "-f", "uvicorn"], capture_output=True)
    time.sleep(2)
    print("       Done")

    # 3. Start DevStat server with no bytecode caching
    print(f"[3/8] Starting DevStat on port {PORT}...")
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:create_app",
         "--host", "127.0.0.1", "--port", str(PORT), "--factory"],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    stderr_lines = []

    # Reader thread for stderr
    import threading
    def read_stderr():
        for line in proc.stderr:
            stderr_lines.append(line.decode("utf-8", errors="replace").rstrip())
    t = threading.Thread(target=read_stderr, daemon=True)
    t.start()

    if not wait_for_server(BASE_URL):
        proc.kill()
        print("       [FAIL] Server did not start within 30s")
        sys.exit(1)
    print(f"       Server PID {proc.pid} — ready")

    import requests

    # List routes for debugging
    try:
        r = requests.get(f"{BASE_URL}/openapi.json", timeout=5)
        if r.status_code == 200:
            paths = list(r.json().get("paths", {}).keys())
            ai_paths = [p for p in paths if "ai" in p]
            print(f"       Available AI routes: {ai_paths}")
    except:
        pass

    # 4. Upload sample data
    print("[4/8] Uploading sample_100.csv...")
    try:
        with open(SAMPLE_CSV, "rb") as f:
            r = requests.post(f"{BASE_URL}/api/data/upload", files={"file": (SAMPLE_CSV.name, f)})
        report("Dataset upload", r.status_code == 200, f"HTTP {r.status_code}: {r.text[:100]}")
        if r.status_code == 200:
            d = r.json()
            print(f"       Dataset: {d['name']} ({d['rows']} rows x {d['cols']} cols)")
    except Exception as e:
        report("Dataset upload", False, str(e))
        proc.kill()
        sys.exit(1)

    # 5. Test GET /api/ai/scan
    print("[5/8] Testing GET /api/ai/scan...")
    try:
        r = requests.get(f"{BASE_URL}/api/ai/scan")
        report("GET /api/ai/scan returns 200", r.status_code == 200, f"HTTP {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            report("scan returns name", bool(data.get("name")), f"name={data.get('name')}")
            report("scan returns columns list", isinstance(data.get("columns"), list) and len(data["columns"]) > 0,
                   f"got {len(data.get('columns', []))} columns")
            report("scan detects binary (sex)", any(c.get("type") == "binary" for c in data.get("columns", [])),
                   "no binary column")
            report("scan detects continuous (age)", any(c.get("type") == "continuous" for c in data.get("columns", [])),
                   "no continuous column")
            print(f"       Dataset: {data['name']} ({data['rows']} rows, {len(data['columns'])} cols)")
    except Exception as e:
        report("GET /api/ai/scan", False, str(e))

    # 6. Test POST /api/ai/parse
    print("[6/8] Testing POST /api/ai/parse...")
    try:
        r = requests.post(f"{BASE_URL}/api/ai/parse", json={
            "question": "Does age differ between male and female patients?"
        })
        report("POST /api/ai/parse returns 200", r.status_code == 200, f"HTTP {r.status_code}: {r.text[:200]}")
        if r.status_code == 200:
            data = r.json()
            plan = data.get("plan", {})
            report("parse returns plan_name", bool(plan.get("plan_name")), f"name={plan.get('plan_name')}")
            report("parse proposes at least 1 test", len(plan.get("tests", [])) >= 1,
                   f"got {len(plan.get('tests', []))} tests")
            if plan.get("tests"):
                t = plan["tests"][0]
                report("test has test_name", bool(t.get("test_name")), f"name={t.get('test_name')}")
                report("test has rationale", bool(t.get("rationale")), "rationale empty")
                report("test has endpoint", bool(t.get("endpoint")), f"endpoint={t.get('endpoint')}")
                report("test has payload", bool(t.get("payload")), "payload empty")
                report("test has fallback", bool(t.get("fallback_test")),
                       f"fallback={t.get('fallback_test')}")
                report("test has assumptions", len(t.get("assumptions", [])) > 0,
                       f"got {len(t.get('assumptions', []))} assumptions")
                print(f"       Plan: {plan['plan_name']}")
                print(f"       Test 1: {t['test_name']}")
                print(f"       Why: {t['rationale'][:80]}...")
    except Exception as e:
        report("POST /api/ai/parse", False, str(e))

    # 7. Test POST /api/ai/execute
    print("[7/8] Testing POST /api/ai/execute...")
    try:
        # First parse to get a plan
        r = requests.post(f"{BASE_URL}/api/ai/parse", json={
            "question": "Describe the distribution of age"
        })
        if r.status_code == 200:
            plan = r.json()["plan"]
            for t in plan.get("tests", []):
                t["user_confirmed"] = True
                t["user_removed"] = False

            r2 = requests.post(f"{BASE_URL}/api/ai/execute", json={"plan": plan})
            report("POST /api/ai/execute returns 200", r2.status_code == 200, f"HTTP {r2.status_code}: {r2.text[:200]}")
            if r2.status_code == 200:
                data = r2.json()
                report("execute returns results list", isinstance(data.get("results"), list),
                       f"got {type(data.get('results'))}")
                report("execute runs at least 1 test", data.get("total", 0) >= 1,
                       f"total={data.get('total')}")
                if data.get("results"):
                    res = data["results"][0]
                    report(f"test '{res.get('test_name', '?')}' runs",
                           res.get("status") in ("success", "error"),
                           f"status={res.get('status')}, error={res.get('error')}")
                    print(f"       Tests: {data['total']} total, {data['success_count']} success")
                    for r3 in data["results"]:
                        icon = "OK" if r3["status"] == "success" else "ERR"
                        fb = f" (fallback: {r3.get('fallback_reason', '')[:40]})" if r3.get("used_fallback") else ""
                        print(f"         [{icon}] {r3['test_name']}{fb}")
    except Exception as e:
        report("POST /api/ai/execute", False, str(e))

    # 8. Test POST /api/ai/analyze (full pipeline)
    print("[8/8] Testing POST /api/ai/analyze (full pipeline)...")
    try:
        r = requests.post(f"{BASE_URL}/api/ai/analyze", json={
            "question": "Is there an association between smoking and hypertension?",
        })
        report("POST /api/ai/analyze returns 200", r.status_code == 200, f"HTTP {r.status_code}: {r.text[:200]}")
        if r.status_code == 200:
            data = r.json()
            report("analyze returns session_id", bool(data.get("session_id")),
                   f"id={data.get('session_id')}")
            report("analyze returns plan", bool(data.get("plan")), "plan missing")
            report("analyze returns results", isinstance(data.get("results"), list) and len(data["results"]) > 0,
                   f"got {len(data.get('results', []))} results")
            report("analyze returns answer with summary",
                   bool(data.get("answer", {}).get("summary")),
                   f"summary={str(data.get('answer', {}).get('summary', ''))[:80]}")
            answer = data.get("answer", {})
            print(f"       Session: {data['session_id']}")
            print(f"       Plan: {data['plan']['plan_name']} ({len(data['plan']['tests'])} test(s))")
            print(f"       Summary: {answer.get('summary', '')[:120]}...")
            if answer.get("detailed_results"):
                for d in answer["detailed_results"]:
                    print(f"         Detail: {d.get('test_name', '?')}")
            if answer.get("limitations"):
                print(f"         Limitations: {answer['limitations'][:80]}...")
    except Exception as e:
        report("POST /api/ai/analyze", False, str(e))

    # ── Summary ──────────────────────────────────────────────────────
    print()
    print("=" * 65)

    # Dump server log if there were errors
    if FAIL > 0:
        log_file = BACKEND_DIR / "logs" / "devstat.log"
        if log_file.exists():
            logs = log_file.read_text(encoding="utf-8").strip().split("\n")
            print(f"\n  [DEBUG] Server log ({len(logs)} lines):")
            for line in logs[-10:]:
                print(f"    {line}")

    total = PASS + FAIL
    if FAIL == 0:
        print(f"  ✅ ALL {PASS}/{PASS} TESTS PASSED")
    else:
        print(f"  ⚠️  {PASS}/{total} PASSED, {FAIL}/{total} FAILED")
        print()
        for e in ERRORS:
            print(f"     - {e}")
    print("=" * 65)

    # Cleanup
    proc.terminate()
    time.sleep(1)
    if proc.poll() is None:
        proc.kill()

    return FAIL


if __name__ == "__main__":
    sys.exit(main())
