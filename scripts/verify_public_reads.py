"""Contract-test the read-only (GET) public API actions against a real account.

For each `documented` public_api GET action it calls the endpoint once and records:
the HTTP status, and whether the response matches the action's declared output schema.
Writes are never called. Response bodies are never stored: only status, error code and
message, and the JSON paths where the response differs from the schema.

Results go to verification/public_reads.json; ingest_openapi.py applies them to the catalog.

The API key is read from BREVO_API_KEY or from a .env file (git-ignored). It is never printed.

Usage: python3 scripts/verify_public_reads.py
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "verification" / "public_reads.json"

# Ids of objects that exist on the test account, used to fill path parameters.
# Anything not listed is skipped, never guessed.
KNOWN_IDS = {
    "listId": 5,
    "folderId": 1,
    "campaignId": 2,
    "identifier": "catalogo.teste@example.com",
}


def api_key():
    if os.environ.get("BREVO_API_KEY"):
        return os.environ["BREVO_API_KEY"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("BREVO_API_KEY="):
                return line.split("=", 1)[1].strip()
    sys.exit("No API key: set BREVO_API_KEY or create .env with BREVO_API_KEY=...")


def build_url(action):
    http = action["execution"]["http"]
    props = action["inputs"].get("properties", {})
    required = set(action["inputs"].get("required", []))
    missing = []

    def fill(match):
        name = match.group(1)
        if name in KNOWN_IDS:
            return urllib.parse.quote(str(KNOWN_IDS[name]), safe="")
        missing.append(name)
        return match.group(0)

    url = re.sub(r"\{\{([^}]+)\}\}", fill, http["url"])
    query = {}
    for name in http.get("query_params", []):
        schema = props.get(name, {})
        if name in ("limit",):
            query[name] = 10
        elif "default" in schema and name in required:
            query[name] = schema["default"]
        elif name in required:
            missing.append(name)
    if missing:
        return None, missing
    return url + ("?" + urllib.parse.urlencode(query) if query else ""), []


def schema_issues(body, outputs):
    schema = outputs.get("schema")
    if not schema or body is None:
        return None
    issues = []
    for e in Draft202012Validator(schema).iter_errors(body):
        issues.append({"path": e.json_path, "rule": e.validator})
        if len(issues) == 5:
            break
    return issues


IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b|\b(?:[0-9a-f]{1,4}:){2,7}[0-9a-f]{1,4}\b", re.I)


def redact(text):
    """Error messages can echo the caller's IP address; never store it."""
    return IP.sub("<ip>", text)


def call(url, key):
    req = urllib.request.Request(url, headers={"api-key": key, "accept": "application/json",
                                               "User-Agent": "brevo-catalog-verify/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            status, raw = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    try:
        body = json.loads(raw) if raw else None
    except ValueError:
        body = None
    return status, body


def main():
    key = api_key()
    # A 401 says nothing about an action, only about the key or the caller's IP; stop early.
    status, body = call("https://api.brevo.com/v3/account", key)
    if status == 401:
        msg = redact(str((body or {}).get("message", "")))
        sys.exit(f"Authentication failed before testing (HTTP 401): {msg[:200]}")
    actions = [json.loads(p.read_text()) for p in sorted((ROOT / "catalog").rglob("*.json"))]
    targets = [a for a in actions if a["execution"]["method"] == "public_api"
               and a["execution"]["http"]["verb"] == "GET" and a["verification"]["level"] == "documented"]

    results = {}
    for a in targets:
        url, missing = build_url(a)
        if not url:
            results[a["id"]] = {"skipped": f"needs {', '.join(missing)}"}
            continue
        status, body = call(url, key)
        rec = {"status": status, "ok": 200 <= status < 300, "date": date.today().isoformat()}
        if rec["ok"]:
            issues = schema_issues(body, a.get("outputs", {}))
            if issues is not None:
                rec["schema_ok"] = not issues
                if issues:
                    rec["schema_issues"] = issues
        elif isinstance(body, dict):
            rec["error_code"] = body.get("code")
            rec["error_message"] = redact(str(body.get("message", "")))[:160]
        results[a["id"]] = rec
        time.sleep(0.25)

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(results, indent=1, sort_keys=True) + "\n")
    ran = [r for r in results.values() if "status" in r]
    ok = [r for r in ran if r["ok"]]
    print(f"{len(targets)} GET actions: {len(ran)} called, {len(ok)} returned 2xx, "
          f"{sum(r.get('schema_ok') is False for r in ok)} differ from their schema, "
          f"{len(results) - len(ran)} skipped (missing ids)")
    for status in sorted({r['status'] for r in ran}):
        print(f"  HTTP {status}: {sum(r['status'] == status for r in ran)}")


if __name__ == "__main__":
    main()
