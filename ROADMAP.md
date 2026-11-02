# Roadmap (5h budget)

Goal: an agent-ready catalog of Brevo business actions. Reliability over raw count: every action says how it was verified.

## Phases

- [x] **0. Contract (0:30)**: action schema, validator, repo layout. Done when the example action validates.
- [x] **1. Map the product (0:45)**: walk the UI menu, list every area and screen, inventory the public API and help center. Done when `coverage/map.md` lists areas with status `todo`.
- [ ] **2. Capture loop (2h15)**: per area, drive the UI, record network traffic, extract candidate actions with an LLM, validate against the schema. Order: contacts and lists, campaigns, automation, transactional, templates, rest.
- [ ] **3. Verify (45m)**: execute safe actions on the free account and upgrade `documented`/`observed` to `executed`. Never trigger real sends or spend credits.
- [ ] **4. Deliver (45m)**: write-up, AI usage, known gaps, scrub captures, email.

## Rules

- Nothing enters `catalog/` without passing `scripts/validate.py`.
- Captures are scrubbed of tokens and credentials before they are stored or sent.
- Gaps are recorded as they are found, not at the end.
