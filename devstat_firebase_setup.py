"""DevStat Firebase setup â€” creates its OWN Firebase project resources (separate from pubmed).

Drive the Firebase Management API with the gcloud access token (no interactive login).
Does NOT print any secret (service-account key content, web apiKey are written to
backend/.env / frontend/.env files only, plus a local SA JSON file).

Creates:
  - Firebase web app + web config (apiKey, authDomain, projectId, appId)
  - Cloud Firestore database (native mode)
  - An Admin SDK service account + a downloaded JSON key file
  - Enables Email/Password, Google, and Phone sign-in providers (best-effort)
"""
import json
import os
import subprocess
import sys

PROJECT = os.environ.get("DEVSTAT_FB_PROJECT", "devstat-fb-789999")
ROOT = r"C:\Users\dell 7390\OneDrive\Desktop\Desktop files\DevStat"
BACKEND_ENV = os.path.join(ROOT, "backend", ".env")
FRONTEND_ENV = os.path.join(ROOT, "frontend", ".env")
SA_KEY_FILE = os.path.join(ROOT, "backend", "devstat-firebase-sa.json")
FB = "https://firebase.googleapis.com/v1beta1"
ITK = "https://identitytoolkit.googleapis.com/v2"
FSTORE = "https://firestore.googleapis.com/v1"


def token():
    return subprocess.run("gcloud auth print-access-token", shell=True,
                          capture_output=True, text=True).stdout.strip()


def req(method, url, token_):
    import urllib.request
    r = urllib.request.Request(url, method=method)
    r.add_header("Authorization", f"Bearer {token_}")
    r.add_header("Content-Type", "application/json")
    r.add_header("x-goog-user-project", PROJECT)
    return r


def call(method, url, tok, body=None):
    import urllib.request, urllib.error
    r = req(method, url, tok)
    data = json.dumps(body).encode() if body is not None else b""
    try:
        with urllib.request.urlopen(r, data=data) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return {"__err__": e.code, "__body__": e.read().decode()[:300]}


def upsert_env(path, pairs):
    lines = open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else []
    idx = {}
    for i, l in enumerate(lines):
        if l.strip() and not l.strip().startswith("#") and "=" in l:
            idx[l.split("=", 1)[0].strip()] = i
    for k, v in pairs.items():
        if k in idx:
            lines[idx[k]] = f"{k}={v}"
        else:
            lines.append(f"{k}={v}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    tok = token()
    if not tok:
        print("ERR: no gcloud token"); return

    # 1) Ensure the project is Firebase-enabled. We use an existing GCP project
    #    and "addFirebase"; if it's already Firebase, GET succeeds.
    proj = call("GET", f"{FB}/projects/{PROJECT}", tok)
    if "__err__" in proj:
        proj = call("POST", f"{FB}/projects/{PROJECT}:addFirebase", tok)
        # addFirebase can be async -> re-GET to confirm the Firebase id.
        proj = call("GET", f"{FB}/projects/{PROJECT}", tok)
    firebase_id = proj.get("projectId") or PROJECT
    print("Firebase projectId:", firebase_id, "| displayName:", proj.get("displayName"))

    # 2) Web app + config
    apps = call("GET", f"{FB}/projects/{PROJECT}/webApps", tok)
    app = None
    for a in apps.get("apps", []):
        if a.get("displayName", "").lower() == "devstat web":
            app = a; break
    if not app:
        app = call("POST", f"{FB}/projects/{PROJECT}/webApps", tok, {"displayName": "DevStat Web"})
        if "__err__" in app:
            print("webApp create error:", app)
            app = {}
    web_app_id = app.get("appId")
    cfg = call("POST", f"{FB}/projects/{PROJECT}/webApps/{web_app_id}/config", tok) if web_app_id else {}
    print("Web appId:", web_app_id)

    # 3) Firestore (native mode), idempotent; database id passed as query param.
    db = call("POST", f"{FSTORE}/projects/{firebase_id}/databases?databaseId=(default)", tok,
              {"type": "FIRESTORE_NATIVE", "locationId": "europe-west1"})
    print("Firestore:", "created" if not isinstance(db, dict) or "__err__" not in db else db)

    # 4) Admin SDK service account + key
    sa_email = f"devstat-admin@{firebase_id}.iam.gserviceaccount.com"
    sa = subprocess.run(f'gcloud iam service-accounts create devstat-admin '
                        f'--project {firebase_id} --display-name "DevStat Admin"',
                        shell=True, capture_output=True, text=True)
    # Idempotent: ignore already-exists; get key
    key = subprocess.run(f'gcloud iam service-accounts keys create "{SA_KEY_FILE}" '
                         f'--iam-account {sa_email} --project {firebase_id}',
                         shell=True, capture_output=True, text=True)
    print("SA key written:", os.path.exists(SA_KEY_FILE))

    # 5) Enable auth providers (Email/Password works via API; Google & Phone
    #    are best enabled in the Firebase console -> Authentication -> Sign-in.)
    authcfg = call("PATCH", f"{ITK}/projects/{firebase_id}/config", tok,
                   {"signIn": {"email": {"enabled": True}, "allowDuplicateEmails": False}})
    print("Auth config (email):", "ok" if "__err__" not in authcfg else authcfg)

    # 6) Write config (values to files only)
    upsert_env(BACKEND_ENV, {
        "DEVSTAT_FIREBASE_PROJECT_ID": firebase_id,
        # Service account as JSON PATH (file). For Cloud Run, mount/set to JSON string later.
        "DEVSTAT_FIREBASE_SERVICE_ACCOUNT": SA_KEY_FILE,
    })
    upsert_env(FRONTEND_ENV, {
        "VITE_FIREBASE_API_KEY": cfg.get("apiKey", ""),
        "VITE_FIREBASE_AUTH_DOMAIN": cfg.get("authDomain", ""),
        "VITE_FIREBASE_PROJECT_ID": cfg.get("projectId", firebase_id),
        "VITE_FIREBASE_STORAGE_BUCKET": cfg.get("storageBucket", ""),
        "VITE_FIREBASE_MESSAGING_SENDER_ID": cfg.get("messagingSenderId", ""),
        "VITE_FIREBASE_APP_ID": cfg.get("appId", web_app_id),
    })
    print("Wrote DEVSTAT_FIREBASE_* to backend/.env and VITE_FIREBASE_* to frontend/.env (values not shown)")
    print("DONE")


if __name__ == "__main__":
    main()

