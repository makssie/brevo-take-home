"""Validate every action in catalog/ against schema/action.schema.json.

Usage: python3 scripts/validate.py
"""
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
schema = json.loads((ROOT / "schema" / "action.schema.json").read_text())
validator = Draft202012Validator(schema)

failed = 0
seen_ids = {}
for path in sorted((ROOT / "catalog").rglob("*.json")):
    action = json.loads(path.read_text())
    errors = list(validator.iter_errors(action))
    action_id = action.get("id")
    if action_id in seen_ids:
        errors.append(f"duplicate id, also in {seen_ids[action_id]}")
    seen_ids[action_id] = path.name
    if errors:
        failed += 1
        print(f"FAIL {path.relative_to(ROOT)}")
        for e in errors:
            print("   ", getattr(e, "message", e))
    else:
        print(f"ok   {path.relative_to(ROOT)}")

# Prose that names another action must name one that exists: an agent will try to call it.
categories = {i.split(".", 1)[0] for i in seen_ids}
for path in sorted((ROOT / "catalog").rglob("*.json")):
    text = re.sub(r"https?://\S+", "", path.read_text())
    for ref in sorted(set(re.findall(r"\b([a-z_]+\.[a-z0-9_]+)\b", text))):
        if ref.split(".", 1)[0] in categories and ref not in seen_ids:
            failed += 1
            print(f"FAIL {path.relative_to(ROOT)}\n    references unknown action {ref}")

print(f"\n{len(seen_ids)} actions, {failed} failed")
sys.exit(1 if failed else 0)
