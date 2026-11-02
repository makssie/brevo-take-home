"""Turn Brevo's public OpenAPI specs into catalog actions (verification: documented).

Downloads the specs listed at https://developers.brevo.com/openapi.json into
.cache/specs, then writes one action file per operation under catalog/<category>/.
Hand-curated actions (an existing action with the same id) are never overwritten.

Usage: python3 scripts/ingest_openapi.py
No credentials needed: the specs are public.
"""
import json
import re
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "specs"
BASE = "https://developers.brevo.com"
METHODS = ("get", "post", "put", "patch", "delete")
MAX_DEPTH = 4


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "brevo-catalog-ingest/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()


def download_specs():
    CACHE.mkdir(parents=True, exist_ok=True)
    index = fetch(f"{BASE}/openapi.json")
    names = re.findall(r'href="openapi/([a-z-]+)\.json"', index)
    for name in names:
        (CACHE / f"{name}.json").write_text(fetch(f"{BASE}/openapi/{name}.json"))
    return names


def snake(text):
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def clean(text, limit=500):
    text = re.sub(r"</?(Note|Warning|br|p|b|i|code)[^>]*>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def resolve(node, spec, depth=0, seen=()):
    """Inline $refs, cut off at MAX_DEPTH and on cycles to keep schemas small."""
    if isinstance(node, list):
        return [resolve(n, spec, depth, seen) for n in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        ref = node["$ref"]
        if ref in seen or depth >= MAX_DEPTH:
            return {"type": "object", "description": f"See {ref.split('/')[-1]}"}
        target = spec
        for part in ref.lstrip("#/").split("/"):
            target = target[part]
        return resolve(target, spec, depth + 1, seen + (ref,))
    return {k: resolve(v, spec, depth, seen) for k, v in node.items() if k not in ("example", "examples")}


def build_inputs(op, path_item, spec):
    props, required, path_params, query_params = {}, [], [], []
    for p in path_item.get("parameters", []) + op.get("parameters", []):
        p = resolve(p, spec)
        if p.get("in") not in ("path", "query"):
            continue
        schema = dict(p.get("schema", {"type": "string"}))
        if p.get("description"):
            schema["description"] = clean(p["description"], 300)
        props[p["name"]] = schema
        (path_params if p["in"] == "path" else query_params).append(p["name"])
        if p.get("required"):
            required.append(p["name"])
    body_props = []
    content = (op.get("requestBody") or {}).get("content", {})
    body = resolve(content.get("application/json", {}).get("schema", {}), spec)
    if body.get("type") == "object" and "properties" in body:
        for k, v in body["properties"].items():
            props.setdefault(k, v)
            body_props.append(k)
        required += [r for r in body.get("required", []) if r not in required]
    elif body:
        props["body"] = body
        body_props.append("body")
        if op["requestBody"].get("required"):
            required.append("body")
    inputs = {"type": "object", "properties": props}
    if required:
        inputs["required"] = required
    return inputs, path_params, query_params, body_props


def build_outputs(op, spec):
    for code, resp in op.get("responses", {}).items():
        if code.startswith("2"):
            resp = resolve(resp, spec)
            schema = resp.get("content", {}).get("application/json", {}).get("schema")
            return {"status": int(code), **({"schema": schema} if schema else {})}
    return {}


def convert(name, spec, verb, path, path_item, op):
    tag = snake((op.get("tags") or ["other"])[0])
    opid = op.get("operationId") or f"{tag}_{verb}_{snake(path)}"
    action_slug = snake(opid.split("_", 1)[1] if "_" in opid else opid)
    inputs, path_params, query_params, body_props = build_inputs(op, path_item, spec)
    url = spec["servers"][0]["url"] + re.sub(r"\{([^}]+)\}", r"{{\1}}", path)
    http = {"verb": verb.upper(), "url": url}
    if query_params:
        http["query_params"] = query_params
    if body_props:
        http["body_template"] = {k: "{{%s}}" % k for k in body_props}
    # Delivery is the irreversible effect an agent must confirm first; DELETE alone missed it.
    sends = verb != "get" and bool(re.search(r"send(?!er)", opid, re.I))
    summary = clean(op.get("summary"), 120)
    detail = clean(op.get("description"), 450)
    description = summary if not detail or detail == summary else f"{summary}. {detail}"
    action = {
        "id": f"{tag}.{action_slug}",
        "name": summary or action_slug.replace("_", " ").capitalize(),
        "category": tag,
        "area": name,
        "description": description,
        "inputs": inputs,
        "outputs": build_outputs(op, spec),
        "execution": {
            "method": "public_api",
            "http": http,
            "auth": "API key in the api-key header, or OAuth 2.0. Not included here.",
        },
        "destructive": verb == "delete" or sends,
        "reversible": not (verb == "delete" or sends),
        **({"side_effects": ["Sends real messages to recipients and consumes plan quota. Cannot be undone."]} if sends else {}),
        "verification": {
            "level": "documented",
            "date": date.today().isoformat(),
            "evidence": f"{BASE}/openapi/{name}.json#{opid}",
            "notes": "Generated from the public OpenAPI spec. Not executed.",
        },
    }
    return apply_public_read(action)


PUBLIC_READS = json.loads(READS.read_text()) if (READS := ROOT / "verification" / "public_reads.json").exists() else {}
ADVICE = {
    400: "A required parameter is missing or invalid. Check inputs before retrying.",
    401: "The API key is missing, wrong, or blocked by IP restrictions. Ask the user to check it.",
    403: "Likely a plan or permission restriction. Tell the user instead of retrying.",
    404: "The feature or resource is not set up on this account. Tell the user.",
}


def apply_public_read(action):
    """Promote an action to executed when verify_public_reads.py called it successfully."""
    r = PUBLIC_READS.get(action["id"])
    if not r or "status" not in r:
        return action
    v = action["verification"]
    if r["ok"]:
        v["level"], v["date"] = "executed", r["date"]
        v["evidence"] = f"GET with an API key on the owner's free account returned HTTP {r['status']}. Spec: {v['evidence']}"
        if r.get("schema_ok") is False:
            where = ", ".join(f"{i['path']} ({i['rule']})" for i in r["schema_issues"])
            v["notes"] = f"Generated from the public OpenAPI spec. The real response differs from the documented output schema at: {where}."
        elif r.get("schema_ok"):
            v["notes"] = "Generated from the public OpenAPI spec. The real response matched the documented output schema."
        else:
            v["notes"] = "Generated from the public OpenAPI spec. Call succeeded; no output schema to compare."
    else:
        message = r.get("error_message") or ""
        if re.search(r"plan|enterprise|corporate|not yet activated|not enabled", message, re.I):
            action["plan_gated"] = f"Refused on the free plan: {message}"
        action.setdefault("errors", []).append({
            "when": "Read-only test call on a free-plan account, with known test ids or no inputs",
            "status": r["status"],
            "response": {"code": r.get("error_code"), "message": r.get("error_message")},
            "agent_should": ADVICE.get(r["status"], "Report the error to the user; do not retry blindly."),
        })
        v["notes"] = f"Generated from the public OpenAPI spec. A read-only call failed on the free account (HTTP {r['status']}); see errors."
    return action


def main():
    names = download_specs()
    existing = {
        json.loads(p.read_text())["id"]
        for p in (ROOT / "catalog").rglob("*.json")
        if not json.loads(p.read_text()).get("verification", {}).get("notes", "").startswith("Generated")
    }
    written = skipped = 0
    for name in names:
        spec = json.loads((CACHE / f"{name}.json").read_text())
        for path, item in spec["paths"].items():
            for verb in METHODS:
                if verb not in item:
                    continue
                action = convert(name, spec, verb, path, item, item[verb])
                if action["id"] in existing:
                    skipped += 1
                    continue
                out = ROOT / "catalog" / action["category"] / f"{action['id'].split('.', 1)[1]}.json"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(action, indent=2, ensure_ascii=False) + "\n")
                written += 1
    print(f"wrote {written} actions, skipped {skipped} hand-curated")


if __name__ == "__main__":
    main()
