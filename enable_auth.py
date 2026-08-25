"""Enable DevStat Firebase Auth sign-in providers via Identity Toolkit API.
PUT creates the auth config (PATCH 404s on an uninitialized project)."""
import json, os, subprocess, urllib.request, urllib.error

PROJECT = os.environ.get("DEVSTAT_FB_PROJECT", "devstat-fb-789999")
ITK = "https://identitytoolkit.googleapis.com/v2"
tok = subprocess.run("gcloud auth print-access-token", shell=True, capture_output=True, text=True).stdout.strip()

body = {
    "signIn": {"allowDuplicateEmails": False},
    "email": {"enabled": True},
    "phone": {"enabled": True},
    "google": {"enabled": True},
}
url = f"{ITK}/projects/{PROJECT}/config"
r = urllib.request.Request(url, method="PUT")
r.add_header("Authorization", f"Bearer {tok}")
r.add_header("Content-Type", "application/json")
r.add_header("x-goog-user-project", PROJECT)
data = json.dumps(body).encode()
try:
    with urllib.request.urlopen(r, data=data) as resp:
        res = json.loads(resp.read().decode())
        print("PUT config ok:", {k: res.get(k) for k in ("email", "phone", "google") if isinstance(res, dict)})
        print("signIn:", res.get("signIn"))
except urllib.error.HTTPError as e:
    print("ERR", e.code, e.read().decode()[:260])
