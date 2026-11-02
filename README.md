# Brevo agent-ready action catalog

A catalog of business actions in Brevo (brevo.com), designed to be consumed by AI agents.

## Layout

- `schema/action.schema.json`: the contract every action must follow.
- `catalog/<category>/<action>.json`: one file per action.
- `scripts/validate.py`: checks every action against the schema and for duplicate ids.
- `scripts/ingest_openapi.py`: generates `documented` actions from Brevo's public OpenAPI.
- `scripts/curated_actions.py`: actions found in the web app's traffic (`executed` / `observed`).
- `scripts/verify_public_reads.py`: contract-tests read-only public actions with an API key; results in `verification/public_reads.json`.
- `scripts/build_dist.py`: builds `dist/catalog.json` (index) and `dist/tools.json` (tool definitions).
- `WRITEUP.md`: approach, AI usage, gaps. Start here.
- `coverage/`: what was explored and what was not; `coverage/metrics.md` has the numbers (`scripts/stats.py`).

## Verification levels

Each action carries `verification.level`:

- `executed`: run on a real free-plan account and it worked.
- `observed`: seen in network traffic from the UI, not executed.
- `documented`: found only in docs or the public API spec.

## Running the validator

```bash
pip install jsonschema
python3 scripts/ingest_openapi.py
python3 scripts/curated_actions.py
python3 scripts/validate.py
python3 scripts/verify_public_reads.py   # optional: needs BREVO_API_KEY in .env (git-ignored)
python3 scripts/build_dist.py
python3 scripts/stats.py
```

No credentials are stored in this repo. Anything that needs a key only describes it.
