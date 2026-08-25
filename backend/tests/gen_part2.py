import json

# Append the _post and check functions to the test file
content = r'''

def _post(path, body, timeout=60):
    """POST JSON body, return (status_code, parsed_response)."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        raw = resp.read().decode("utf-8")
        if not raw.strip():
            return (resp.status, "EMPTY")
        return (resp.status, json.loads(raw))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return (e.code, json.loads(raw))
        except json.JSONDecodeError:
            return (e.code, raw.strip() or ("HTTP %d" % e.code))
    except Exception as e:
        return (0, str(e))


def check(name, path, body, expect_status=200, expect_blocked=None):
    """Run one test case and record pass/fail."""
    global passed, failed, total_tests
    total_tests += 1
    status, data = _post(path, body)
    ok = True
    reasons = []
    if status != expect_status:
        ok = False
        reasons.append("status=%d (expect %d)" % (status, expect_status))
    if isinstance(data, dict):
        if expect_blocked is True and not data.get("blocked"):
            ok = False
            reasons.append("want blocked=True, got %s" % data.get("blocked"))
        elif expect_blocked is False and data.get("blocked"):
            ok = False
            reasons.append("want not blocked, got blocked=True")
    elif isinstance(data, str) and data == "EMPTY":
        ok = False
        reasons.append("empty response body")
    if ok:
        passed += 1
        print("  [PASS]", name)
    else:
        failed += 1
        d = data if isinstance(data, str) else json.dumps(data, indent=2)[:200]
        print("  [FAIL]", name, "|", " | ".join(reasons))
        if reasons:
            print("     data:", d)
'''

with open('test_all_endpoints.py', 'a') as f:
    f.write(content)
print("Part 2 done (appended helper functions)")
