"""Build the agent-facing artifacts from catalog/.

dist/catalog.json  small index: what exists, how trustworthy, how it runs.
dist/tools.json    one tool definition per action (name, description, input_schema),
                   in the shape LLM tool-calling APIs expect.

Usage: python3 scripts/build_dist.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEVEL_ORDER = {"executed": 0, "observed": 1, "documented": 2}


def tool_name(action_id):
    return re.sub(r"[^a-zA-Z0-9_-]", "_", action_id.replace(".", "__"))[:64]


def one_line(text, limit=220):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def main():
    actions = [json.loads(p.read_text()) for p in sorted((ROOT / "catalog").rglob("*.json"))]
    actions.sort(key=lambda a: (LEVEL_ORDER[a["verification"]["level"]], a["category"], a["id"]))

    index, tools, names = [], [], set()
    for a in actions:
        name = tool_name(a["id"])
        assert name not in names, f"tool name collision: {name}"
        names.add(name)
        index.append({
            "id": a["id"],
            "name": a["name"],
            "category": a["category"],
            "summary": one_line(a["description"]),
            "verification": a["verification"]["level"],
            "method": a["execution"]["method"],
            "destructive": a.get("destructive", False),
            "plan_gated": a.get("plan_gated"),
            "file": str(next((ROOT / "catalog").rglob(f"{a['id'].split('.', 1)[1]}.json")).relative_to(ROOT)),
        })
        description = one_line(a["description"], 900)
        flags = [f"[verification: {a['verification']['level']}]"]
        if a.get("destructive"):
            flags.append("[DESTRUCTIVE: confirm with the user first]")
        if a.get("plan_gated"):
            flags.append("[paid plan]")
        tools.append({"name": name, "description": f"{' '.join(flags)} {description}", "input_schema": a["inputs"]})

    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    (dist / "catalog.json").write_text(json.dumps({"count": len(index), "actions": index}, indent=1, ensure_ascii=False) + "\n")
    (dist / "tools.json").write_text(json.dumps(tools, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(index)} actions -> dist/catalog.json ({(dist / 'catalog.json').stat().st_size // 1024} KB), "
          f"dist/tools.json ({(dist / 'tools.json').stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
