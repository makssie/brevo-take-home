# Internal endpoints observed (phase 2)

Read-only harvest of what each screen calls on load (page `performance` entries, query strings dropped). These are candidates for catalog actions, not yet actions: payload and response shapes are still unknown unless marked captured.

## Captured (request and response seen)

| Action | Endpoint | Notes |
|---|---|---|
| Create contact | `POST contacts-api.brevo.com/contact/backend/contacts/add-contact` | Body `{email, listIds, attributes}`. Response `{contact_id}`. In `catalog/contacts/create_contact.json`. |
| Check duplicate | `GET contacts-api.brevo.com/contact/backend/contacts/is_duplicate_contact` | Returns `{is_exist, contactId}`. Called before create. |

## Seen on screen load (shape not captured)

| Area | Endpoints |
|---|---|
| Lists | `contacts-api-v2.brevo.com/lists/get-lists`, `.../lists/get-folders` |
| Segments | `segments-api.brevo.com/segment/listing`, `.../segment/folder/listing`, `.../segment/count`, `.../segment/query` |
| Campaigns | `email-campaigns-backend.brevo.com/email-campaign/api/campaigns`, `.../email-campaign/api/config`, `folder-engine.brevo.com/folders/layers`, `tag-engine.brevo.com/tags` |
| Templates | `email-campaigns-backend.brevo.com/email-template/api/templates`, `editor-api.brevo.com/editor-api/localization/languages` |
| Automations | `workflow-apis.brevo.com/v1/workflow/metaInfo`, `.../v1/sidebar/contactCount`, `automation-engine-http-public.brevo.com/processing-details` |
| Companies (CRM) | `crm-backend-api.brevo.com/crm/backend/companies`, `.../crm/backend/attributes` |

## Findings

- More than 10 distinct backend hosts across 6 screens. Hosts follow `<domain>-api` or `<domain>-backend`.
- Two contacts services coexist: `contacts-api` and `contacts-api-v2`. Lists use v2, contact creation uses v1. Version split is per feature, not per product.
- Request bodies are sent through a `Request` object, so capture must clone the request, not only read `init.body`.
- Test data left in the account: contacts `catalogo.teste@example.com` and `catalogo.teste2@example.com`.

## Phase 2b: UI-only areas (public API has no equivalent)

Gap analysis against the 287 public-API actions: segments had 1 read action and no create/update/delete; automations, landing pages, forms, tags, meetings and saved views had none.

| Area | Captured | Not captured |
|---|---|---|
| Segments | create, list, get, folders, filterable fields, count and preview by filter | update, delete, move between folders, per-operator rules by data type |
| Automations | create empty, list, get, list all step types, add trigger, row menu (rename, duplicate, delete, tag, report, logs) | save trigger settings, add action and condition steps, activate, pause, delete (not executed on purpose) |

## Findings from phase 2

- **Auth is a session cookie.** Internal GET endpoints answered 200 when called from inside the logged-in app page with `credentials: include` and no extra headers. Not tested outside a browser.
- **Replay beats clicking.** After one UI capture of a write, reads can be replayed from the page in seconds. This is how list/get actions were verified.
- **Servers explain their own contract.** A missing query parameter returns 422 `invalid query parameter: <name>`, which lets parameters be discovered by trial.
- **`unified-ddl` is a 250 KB definition of the automation builder.** The per-step settings schema is inside it and would be the next thing to parse.
- **Account state matters.** The test account shows "suspended for marketing emails", so anything that sends email through automations or campaigns may be blocked regardless of the call being correct.
- **Output hygiene.** The browser tool blocks results that echo query strings, so captures drop them. Request headers are never recorded, so no token reaches this repo.

## Phase 2c: campaigns and forms

| Area | Captured | Not captured |
|---|---|---|
| Email campaigns | create draft, set subject, count and save recipients, set HTML content, list; the 4-part readiness model (sender, recipients, subject, design) | sender change, additional settings, drag-and-drop and simple editors, templates as a starting point, schedule/send (not executed on purpose), SMS and AI-generated campaigns |
| Forms | create sign-up form, list, account state | form designer edits, Unsubscribe and Profile update types, pop-up forms (paid) |
| Templates | listing endpoint seen; replay returned `TEMPLATE_PARAM_INVALID` (parameter unknown) | everything else |

Paid-plan features seen as locked (crown icon): A/B test, campaign tags and folders, WhatsApp, Push and Pop-up campaigns, Landing pages, pop-up forms, automation tags.

Findings:

- **Campaign creation is a state machine.** The draft exists after one call with only a name; each later call fills one of four parts. A campaign is schedulable when all four show a green check.
- **Marketing sub-apps are separate pages.** The campaign setup, the HTML editor and the form designer each load as their own app, which discards any script injected earlier. Capture has to be re-armed on every full page load.
- **Ids differ by service.** Campaigns, segments and workflows use integers; forms use 24-character string ids.
- **`userHash` in the HTML store call** is sent by the editor and its origin is unknown. It is the main reason that action may not be replayable outside the page.
