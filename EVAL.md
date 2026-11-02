# Blind-agent evaluation

**Question:** could an agent act on this catalog without a human double-checking? Instead of asserting it, I measured it.

**Setup:** a fresh subagent (Claude Opus 5.5, no access to this conversation, the scripts, the coverage notes or the write-up) reads only `dist/` and `catalog/`. It has a browser session cookie but no public API key, which is the realistic case for an agent operating the product like a user. It plans six tasks, three of them the brief's own examples, and must flag every gap. It does not execute anything; I compare its plans with what I captured on the live account.

| Task | What it tests |
|---|---|
| T1 | Create a contact and add it to a named list (brief examples) |
| T2 | Same, when the email already exists (error recovery) |
| T3 | Draft an email campaign to all subscribers, do not send (brief example) |
| T4 | Automation triggered by "added to list 5" |
| T5 | Delete an automation (destructive) |
| T6 | Send a campaign now (irreversible) |

## Round 1

Only T1 would work on the first try. Problems found, most severe first:

1. **Unsafe flags.** `email_campaigns.send_email_campaign_now` (generated from the spec) was marked `destructive: false, reversible: true`. An agent trusting the flags would send email without asking. The generator only flagged DELETE.
2. **Dead ends in recovery advice.** On a duplicate email, `create_contact` told the agent to use the public API, which it cannot call. No internal lookup existed.
3. **Blocking input with no source.** `set_campaign_html_content` required `userHash` with "origin not determined".
4. **A stale duplicate.** A renamed action left its old file behind, pointing at an id that no longer existed.
5. **Wrong enum.** `list_filterable_fields` omitted `subscription_status`, the data type its own example uses.
6. Missing steps: configuring an automation trigger, setting the campaign sender.

## Fixes

| Problem | Fix | How it was confirmed |
|---|---|---|
| 1 | Generator marks any non-GET operation whose id contains "send" (not "sender") as destructive and irreversible, with a side effect. 16 send actions now flagged. | Count and spot check in `dist/catalog.json` |
| 2 | New action `contacts.check_duplicate_contact` (internal, returns `contactId`). Error advice now chains to it. | Replayed on the live account: `{is_exist: true, contactId: 2}` |
| 3 | New action `email_campaigns.get_editor_account`, the source of `userHash`. | Replayed: response keys include `userHash` |
| 4 | Stale file removed. `validate.py` now fails when any action names an action id that does not exist. | Validator run |
| 5 | Enum replaced by a description listing observed values, including `subscription_status`. | Matches the captured segment filter |
| 6 | Not fixed: needs more UI capture. Recorded as known gaps. | |

## Round 2

Same six tasks, a new subagent with no memory of round 1.

| Task | Round 1 (first-try confidence) | Round 2 verdict |
|---|---|---|
| T1 create contact + add to list | medium-high | **Complete**, medium |
| T2 duplicate email | low: recovery pointed at an API it could not call | **Complete** for list membership via `check_duplicate_contact`; partial for updating the name (public API only) |
| T3 campaign draft, no send | low: blocked by `userHash` | **Complete**, medium: every step has a callable action |
| T4 automation on "added to list 5" | low | **Partial**: trigger placed, list choice and activation not captured |
| T5 delete automation | hand-off | **Complete**: confirms with the user, then hands off the UI steps |
| T6 send now | low, and the flags would have allowed a send without asking | **Complete**: flags force confirmation; sending handed to the user |

Remaining problems it ranked, most severe first:

1. Automation trigger settings, extra steps and activation are not captured.
2. No internal read-back for one campaign or one contact (only public API versions exist), so readiness before a send cannot be fully checked.
3. Three paths rest on untested assumptions: replaying the HTML store with a fetched `userHash`, `create_contact` with non-empty `listIds`, and whether `included_segment_names` is required.
4. Updating a contact is public API only, with no UI steps.
5. The marketing-email suspension is not exposed by any endpoint found.

**Caveat:** verdicts are the agent's own assessment of its plan, checked by me against the captured calls. The plans were not executed end to end; doing so is the obvious next step.
