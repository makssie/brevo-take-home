"""Hand-curated actions found by reverse engineering the Brevo web app (internal API).

Each entry was observed in network traffic while using the UI on a free account, and
re-checked by replaying the call from inside the logged-in page where marked.
Writes catalog/<category>/<name>.json. Run after ingest_openapi.py; ids listed here win.

Usage: python3 scripts/curated_actions.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATE = "2026-11-02"
AUTH = (
    "Cookie session of the logged-in app.brevo.com user, sent with the request "
    "(fetch credentials: include). No API key. Replayed from inside the app page only; "
    "behavior from outside a browser (CSRF, CORS, session expiry) was not tested."
)
SEGMENTS = "https://segments-api.brevo.com"
WORKFLOWS = "https://workflow-apis.brevo.com/v1/workflow"
SUSPENDED = ("Observed on the test account: a banner says it is suspended for marketing emails, so activating "
             "a workflow that sends email is expected to be blocked. Not tested.")
CONTACTS = "https://contacts-api.brevo.com"

FE_QUERY = {
    "type": "object",
    "description": (
        "Filter tree. An 'or' list of groups; each group has an 'and' list of conditions. "
        "A condition is {contact: {field, dataType, operator, value: [..]}, isValidated: true}. "
        "Valid fields and data types come from segments.list_filterable_fields."
    ),
    "example": {
        "or": [{"and": [{"contact": {"field": "email_blacklisted", "dataType": "subscription_status",
                                     "operator": "subscribed", "value": ["subscribed"]},
                         "isValidated": True}]}]
    },
}


def action(id_, name, description, inputs, execution, outputs=None, how="ui", notes="",
           destructive=False, reversible=True, side_effects=None, preconditions=None):
    category, slug = id_.split(".", 1)
    level_note = {
        "ui": "Executed through the UI with request capture.",
        "replay": "Observed in UI traffic, then replayed from inside the logged-in page.",
        "menu": "Option seen in the UI menu. Not executed.",
    }[how]
    if execution.get("method") == "ui_only":
        execution = dict(execution)
    else:
        execution = {"method": "internal_api", "auth": AUTH, **execution}
    a = {
        "id": id_, "name": name, "category": category, "area": "web-app-internal",
        "description": description,
        "inputs": inputs, "outputs": outputs or {},
        "execution": execution,
        "destructive": destructive, "reversible": reversible,
        "verification": {"level": "observed" if how == "menu" else "executed", "date": DATE,
                         "evidence": "Own free account, 2026-11-02.",
                         "notes": f"{level_note} {notes}".strip()},
    }
    if side_effects:
        a["side_effects"] = side_effects
    if preconditions:
        a["preconditions"] = preconditions
    return a


def obj(props, required=()):
    o = {"type": "object", "properties": props}
    if required:
        o["required"] = list(required)
    return o


ACTIONS = [
    action(
        "segments.create_segment", "Create a segment",
        "Create a saved, dynamic segment of contacts from a filter. Use when the goal is a reusable "
        "audience defined by rules (subscription status, attributes, list membership) rather than a fixed list. "
        "The public API cannot do this.",
        obj({"name": {"type": "string", "maxLength": 50},
             "fe_query": FE_QUERY,
             "category_id": {"type": "string", "description": "Folder id from segments.list_segment_folders."},
             "source": {"type": "string", "default": "listing"},
             "template_used": {"type": "string", "description": "Optional. e.g. ALL_EMAIL_SUBSCRIBERS."},
             "template_group": {"type": "string", "description": "Optional. e.g. EMAIL_MARKETING."}},
            ["name", "fe_query", "category_id"]),
        {"http": {"verb": "POST", "url": f"{SEGMENTS}/segment",
                  "body_template": {"name": "{{name}}", "fe_query": "{{fe_query}}", "category_id": "{{category_id}}",
                                    "source": "{{source}}", "template_used": "{{template_used}}",
                                    "template_group": "{{template_group}}"}}},
        {"status": 201, "schema": obj({"data": obj({"id": {"type": "integer"}}), "message": {"type": "string"}})},
        side_effects=["Creates a segment; the count is computed asynchronously (count_metadata.status in_progress)."],
        notes="Created the segment 'Catalogo teste assinantes' (id 1).",
        preconditions=["A folder exists (the default 'My segments' folder always does)."],
    ),
    action(
        "segments.list_segments", "List segments",
        "List saved segments with id, name, folder and last update. Use to find a segment id.",
        obj({"limit": {"type": "integer", "default": 20}, "page": {"type": "integer", "default": 1}},
            ["limit", "page"]),
        {"http": {"verb": "GET", "url": f"{SEGMENTS}/segment/listing", "query_params": ["limit", "page"]}},
        {"status": 200, "schema": obj({"data": {"type": "array", "items": obj({
            "id": {"type": "integer"}, "name": {"type": "string"}, "category_id": {"type": "string"},
            "updated_at": {"type": "string"}, "count_metadata": {"type": "object"}})},
            "metadata": {"type": "object"}})},
        how="replay",
        notes="Both limit and page are required: the server answers 422 'invalid query parameter' otherwise.",
        reversible=True,
    ),
    action(
        "segments.get_segment", "Get a segment",
        "Get the name and filter of one segment by id. Use before editing or reusing its filter.",
        obj({"id": {"type": "integer"}}, ["id"]),
        {"http": {"verb": "GET", "url": f"{SEGMENTS}/segment/{{{{id}}}}"}},
        {"status": 200, "schema": obj({"data": obj({"name": {"type": "string"}, "fe_query": FE_QUERY})})},
        how="replay",
    ),
    action(
        "segments.list_segment_folders", "List segment folders",
        "List the folders that hold segments. A folder id is required to create a segment.",
        obj({}),
        {"http": {"verb": "GET", "url": f"{SEGMENTS}/segment/folder/listing"}},
        {"status": 200, "schema": obj({"data": {"type": "array", "items": obj({
            "id": {"type": "string"}, "name": {"type": "string"}, "default": {"type": "boolean"}})}})},
        how="replay",
    ),
    action(
        "segments.list_filterable_fields", "List fields a segment can filter on",
        "List contact attributes and system fields that can be used in a segment filter, with the data type of each. "
        "Use before building fe_query so the field and operator are valid.",
        obj({}),
        {"http": {"verb": "GET", "url": f"{CONTACTS}/contact/backend/segment/properties"}},
        {"status": 200, "schema": obj({"data": obj({
            "attributes": {"type": "array", "items": obj({
                "field": {"type": "string"}, "field_key": {"type": "string"},
                "dataType": {"type": "string", "description": (
                    "Observed: email, text, category, date, boolean, list, flagged, last_modified, entered. "
                    "Subscription filters use dataType 'subscription_status' (field email_blacklisted, operator subscribed), "
                    "which this endpoint does not list.")}})},
            "active_channels": {"type": "array"}})})},
        how="replay",
        notes="Free account returned 24 fields. Operators per data type were not enumerated.",
    ),
    action(
        "segments.count_matching_contacts", "Count contacts matching a filter",
        "Return how many contacts match a filter without saving a segment. Use to preview audience size.",
        obj({"fe_query": FE_QUERY, "searchBy": {"type": "string", "default": ""}}, ["fe_query"]),
        {"http": {"verb": "POST", "url": f"{CONTACTS}/contact/backend/segment/contact/count",
                  "body_template": {"fe_query": "{{fe_query}}", "searchBy": "{{searchBy}}"}}},
        {"status": 200, "schema": obj({"contact_count": {"type": "integer"}, "total_count": {"type": "integer"}})},
        notes="An empty fe_query ({}) counts all contacts.",
    ),
    action(
        "segments.preview_matching_contacts", "Preview contacts matching a filter",
        "Return a page of the contacts that match a filter, without saving a segment.",
        obj({"fe_query": FE_QUERY, "page": {"type": "integer", "default": 1},
             "limit": {"type": "integer", "default": 20}, "force_refresh": {"type": "boolean", "default": True}},
            ["fe_query"]),
        {"http": {"verb": "POST", "url": f"{CONTACTS}/contact/backend/segment/query",
                  "body_template": {"fe_query": "{{fe_query}}", "page": "{{page}}", "limit": "{{limit}}",
                                    "force_refresh": "{{force_refresh}}"}}},
        {"status": 200, "schema": obj({"data": {"type": "array", "items": obj({
            "id": {"type": "integer"}, "email": {"type": "string"}, "attributes": {"type": "object"},
            "entered": {"type": "string"}, "last_modified": {"type": "string"}})}})},
    ),
    action(
        "automations.create_workflow", "Create an empty automation",
        "Create a new empty automation (workflow) in draft/inactive state. It has no trigger yet. Use as the first step "
        "of building an automation; then add a trigger with automations.add_trigger. The public API has no automation endpoints.",
        obj({"workflow_name": {"type": "string", "default": "Automation"},
             "workflow_desc": {"type": "string", "default": ""},
             "multiple_trigger": {"type": "boolean", "default": False},
             "is_default": {"type": "boolean", "default": True}}),
        {"http": {"verb": "POST", "url": f"{WORKFLOWS}/createcustom",
                  "body_template": {"workflow_name": "{{workflow_name}}", "workflow_desc": "{{workflow_desc}}",
                                    "multiple_trigger": "{{multiple_trigger}}", "is_default": "{{is_default}}"}}},
        {"status": 200, "schema": obj({"workflow_id": {"type": "integer"}})},
        side_effects=["Creates an inactive workflow named 'Automation #<n>' (the UI ignores workflow_name and numbers it)."],
        notes="Created 'Automation #1' via 'Create from scratch'. " + SUSPENDED,
    ),
    action(
        "automations.list_workflows", "List automations",
        "List all automations with id, name, active/paused state and contact counters (started, holding, completed, stopped).",
        obj({}),
        {"http": {"verb": "GET", "url": f"{WORKFLOWS}/listing"}},
        {"status": 200, "schema": obj({"total_fetched_workflows_count": {"type": "integer"}, "workflows": {
            "type": "array", "items": obj({
                "id": {"type": "integer"}, "scenario_name": {"type": "string"}, "active": {"type": "boolean"},
                "paused": {"type": "boolean"}, "status": {"type": "string"}, "started_users": {"type": "integer"},
                "holding_users": {"type": "integer"}, "completed_users": {"type": "integer"},
                "stopped_users": {"type": "integer"}, "updated_at": {"type": "integer", "description": "Epoch ms."}})}})},
        how="replay",
        notes="Pagination and filters (status tab, tags, search) were not explored; the UI loads everything.",
    ),
    action(
        "automations.get_workflow", "Get an automation with its triggers",
        "Get one automation's name, status and the triggers placed on it, including whether each trigger is fully configured (is_complete).",
        obj({"id": {"type": "integer"}}, ["id"]),
        {"http": {"verb": "GET", "url": f"{WORKFLOWS}/{{{{id}}}}/description"}},
        {"status": 200, "schema": obj({
            "id": {"type": "integer"}, "name": {"type": "string"}, "description": {"type": "string"},
            "is_active": {"type": "boolean"}, "is_paused": {"type": "boolean"}, "status": {"type": "string"},
            "triggers": {"type": "array", "items": obj({
                "trigger_point_id": {"type": "integer"}, "event_name": {"type": "string"},
                "is_complete": {"type": "boolean"}, "internal_action_id": {"type": "integer"},
                "source": {"type": "string"}})}})},
        how="replay",
    ),
    action(
        "automations.list_step_types", "List the trigger, action and condition types an automation can use",
        "Return every building block of the automation builder. Use before adding steps, because add_trigger needs a "
        "trigger key, its source category and its internal_action_id from this response. Observed on the free account: "
        "triggers " + json.dumps({
            "contacts": ["added_to_lists", "removed_from_lists", "contact_match_custom_filter", "contact_match_one_segment",
                         "automation_date_attribute_contact_trigger_modified", "manual_trigger"],
            "email": ["email_opened", "email_clicked", "email_unsubscribed"], "forms": ["form_submitted"],
            "deals": ["deal_created", "deal_stage_updated", "task_created", "task_completed"],
            "product": ["back_in_stock", "price_drop", "back_in_stock_subscribed", "back_in_stock_expired"],
            "website": ["page_visited"], "coupon": ["unique_coupon_sent"], "WhatsApp": ["whatsapp-reply"],
            "custom": ["custom"]}) + "; actions " + json.dumps({
            "contacts": ["add_to_list", "remove_from_list", "update_contact_attribute", "blocklist_contact",
                         "assign_a_user_to_a_contact", "delete_a_contact", "update_company_attribute"],
            "messaging": ["send_email", "send_sms", "sales_send_one_to_one_email_from_mailbox", "send_whatsapp",
                          "email_notify", "migrated_email_notify"],
            "deals": ["create_task", "update_deal_attribute", "copy_a_deal", "create_a_deal"],
            "Automations": ["start_another_workflow", "go_to_step"], "Webhooks": ["call_webhook"],
            "product": ["remove_product_contact_association"]}) + "; conditions "
        + json.dumps(["add_delay", "if_else_bool_segmentation", "percentage_split", "wait_until"]) + ".",
        obj({}),
        {"http": {"verb": "GET", "url": f"{WORKFLOWS}/getCategoryData"}},
        {"status": 200, "schema": obj({
            "trigger_categories": {"type": "object", "description": "category -> list of {key, action_type, internal_action_id, source, label}"},
            "action_categories": {"type": "object"}, "condition_categories": {"type": "object"}})},
        how="replay",
        notes="Labels are i18n keys, not readable names. Per-step configuration fields live in the 250 KB "
              "GET /v1/workflow/unified-ddl definition, which was not parsed.",
    ),
    action(
        "automations.add_trigger", "Add a trigger to an automation",
        "Place the entry trigger on an automation. The trigger exists but is incomplete (is_complete false) until its own "
        "settings are saved, for example the list for added_to_lists. Get valid keys from automations.list_step_types.",
        obj({"id": {"type": "integer", "description": "Workflow id."},
             "trigger_name": {"type": "string", "description": "Block key, e.g. added_to_lists."},
             "multiple_entry": {"type": "boolean", "default": False,
                                "description": "Let the same contact enter more than once."},
             "internal_action_id": {"type": "integer", "description": "From list_step_types. 1 for added_to_lists."},
             "source": {"type": "string", "description": "Trigger category, e.g. contacts."}},
            ["id", "trigger_name", "internal_action_id", "source"]),
        {"http": {"verb": "POST", "url": f"{WORKFLOWS}/{{{{id}}}}/trigger",
                  "body_template": {"trigger_name": "{{trigger_name}}", "multiple_entry": "{{multiple_entry}}",
                                    "internal_action_id": "{{internal_action_id}}", "source": "{{source}}"}}},
        {"status": 200, "schema": obj({"status": {"type": "boolean"}, "start_point_id": {"type": "integer"}})},
        preconditions=["A workflow exists (automations.create_workflow)."],
        notes="Executed by dragging 'Contact added to list' onto the canvas. The call that saves the trigger's "
              "settings (choosing the list) was not captured: no list existed to pick. Adding action and condition steps was not captured.",
    ),
    action(
        "automations.rename_workflow", "Rename an automation",
        "Rename an automation from the row menu on the Automations page.",
        obj({"id": {"type": "integer"}, "name": {"type": "string"}}, ["id", "name"]),
        {"method": "ui_only", "ui_steps": ["Open Automations > Workflows.", "Open the row's three-dot menu.",
                                           "Click 'Rename'.", "Enter the new name and confirm."]},
        how="menu",
    ),
    action(
        "automations.duplicate_workflow", "Duplicate an automation",
        "Copy an existing automation with its steps, from the row menu.",
        obj({"id": {"type": "integer"}}, ["id"]),
        {"method": "ui_only", "ui_steps": ["Open Automations > Workflows.", "Open the row's three-dot menu.",
                                           "Click 'Duplicate'."]},
        how="menu",
    ),
    action(
        "automations.delete_workflow", "Delete an automation",
        "Delete an automation from the row menu. Treat as irreversible and confirm with the user first.",
        obj({"id": {"type": "integer"}}, ["id"]),
        {"method": "ui_only", "ui_steps": ["Open Automations > Workflows.", "Open the row's three-dot menu.",
                                           "Click 'Delete' and confirm."]},
        how="menu", destructive=True, reversible=False,
        notes="Deliberately not executed during exploration: deleting data was left to the account owner.",
    ),
    {**action(
        "automations.assign_tag", "Assign a tag to an automation",
        "Tag an automation to organize and filter the list.",
        obj({"id": {"type": "integer"}, "tag": {"type": "string"}}, ["id", "tag"]),
        {"method": "ui_only", "ui_steps": ["Open the row's three-dot menu.", "Click 'Assign a tag'."]},
        how="menu"), "plan_gated": "Paid plan (the option shows a crown icon on the free plan)."},
    action(
        "email_campaigns.create_campaign_draft", "Create an email campaign draft",
        "Create a regular email campaign in Draft state with only a name. First step of building a campaign; then set "
        "subject, recipients and content. A campaign is ready to schedule when all four parts (sender, recipients, subject, design) are complete. "
        "On the free plan A/B tests, tags and folders are paid features.",
        obj({"camp_name": {"type": "string", "maxLength": 128},
             "folder_path": {"type": "string", "default": "", "description": "Paid plan feature."},
             "tag_ids": {"type": "array", "items": {"type": "integer"}, "default": [], "description": "Paid plan feature."}},
            ["camp_name"]),
        {"http": {"verb": "POST", "url": "https://email-campaigns-backend.brevo.com/email-campaign/api/regular/setup",
                  "body_template": {"camp_name": "{{camp_name}}", "folder_path": "{{folder_path}}", "tag_ids": "{{tag_ids}}"}}},
        {"status": 201, "schema": obj({"id": {"type": "integer", "description": "Campaign id used by every later step."}})},
        side_effects=["Creates a draft. The sender defaults to the account owner. Nothing is sent."],
        notes="Created two drafts. The web UI creates the campaign here before any other field is filled.",
    ),
    action(
        "email_campaigns.set_campaign_subject", "Set a campaign's subject line",
        "Set the subject (and optional preview text) of a draft campaign.",
        obj({"id": {"type": "integer"}, "subject": {"type": "string"},
             "preheaderSetup": {"type": ["object", "null"], "default": None, "description": "Preview text settings. Shape not captured."},
             "subjectLineSource": {"type": "string", "default": "manual", "description": "'manual' when typed by a person."},
             "subjectModifiedAfterAIUse": {"type": "boolean", "default": False}},
            ["id", "subject"]),
        {"http": {"verb": "POST", "url": "https://email-campaigns-backend.brevo.com/email-campaign/api/{{id}}/save-subject",
                  "body_template": {"subject": "{{subject}}", "preheaderSetup": "{{preheaderSetup}}",
                                    "subjectLineSource": "{{subjectLineSource}}",
                                    "subjectModifiedAfterAIUse": "{{subjectModifiedAfterAIUse}}"}}},
        {"status": 204},
        preconditions=["A campaign draft exists."],
    ),
    action(
        "email_campaigns.preview_recipient_count", "Count recipients for a campaign audience",
        "Return how many contacts an audience selection would reach, before saving it. Use to check against the plan's remaining email quota.",
        obj({"id": {"type": "integer"},
             "included_list_ids": {"type": "array", "items": {"type": "integer"}, "default": []},
             "included_segment_ids": {"type": "array", "items": {"type": "integer"}, "default": []},
             "excluded_list_ids": {"type": "array", "items": {"type": "integer"}, "default": []},
             "excluded_segment_ids": {"type": "array", "items": {"type": "integer"}, "default": []},
             "included_contacts": {"type": "array", "default": []}, "excluded_contacts": {"type": "array", "default": []},
             "apply_unengage_filter": {"type": "boolean", "default": False,
                                       "description": "Skip contacts who did not engage recently."},
             "filter_fe_query": {"type": "object", "default": {}}}, ["id"]),
        {"http": {"verb": "POST", "url": "https://email-campaigns-backend.brevo.com/email-campaign/api/{{id}}/recipient-count",
                  "body_template": {k: "{{%s}}" % k for k in (
                      "included_list_ids", "included_segment_ids", "excluded_list_ids", "excluded_segment_ids",
                      "included_contacts", "excluded_contacts", "apply_unengage_filter", "filter_fe_query")}}},
        {"status": 200, "schema": obj({"still_to_process": {"type": "integer"}})},
    ),
    action(
        "email_campaigns.set_campaign_recipients", "Set a campaign's recipients",
        "Choose who receives a draft campaign: lists, segments or individual contacts, with exclusions. Replaces the previous selection. "
        "Use segments.create_segment first to target a rule-based audience.",
        obj({"id": {"type": "integer"},
             "included_list_ids": {"type": "array", "items": {"type": "integer"}, "default": []},
             "included_segment_ids": {"type": "array", "items": {"type": "integer"}, "default": []},
             "included_segment_names": {"type": "array", "items": {"type": "string"},
                                        "description": "Sent by the UI next to the ids. Whether the server needs it was not tested."},
             "excluded_list_ids": {"type": "array", "items": {"type": "integer"}, "default": []},
             "excluded_segment_ids": {"type": "array", "items": {"type": "integer"}, "default": []},
             "included_contacts": {"type": "array", "default": []}, "excluded_contacts": {"type": "array", "default": []},
             "apply_unengage_filter": {"type": "boolean", "default": False},
             "filter_fe_query": {"type": "object", "default": {}}}, ["id"]),
        {"http": {"verb": "POST", "url": "https://email-campaigns-backend.brevo.com/email-campaign/api/{{id}}/save-recipient",
                  "body_template": {k: "{{%s}}" % k for k in (
                      "included_list_ids", "included_segment_ids", "included_segment_names", "excluded_list_ids",
                      "excluded_segment_ids", "included_contacts", "excluded_contacts", "apply_unengage_filter",
                      "filter_fe_query")}}},
        {"status": 200, "schema": obj({"still_to_process": {"type": "integer"}, "blacklistedRemoved": {"type": "boolean"}})},
        preconditions=["A campaign draft exists.", "The lists or segments exist."],
        notes="Saved the segment 'Catalogo teste assinantes' (3 recipients). Nothing was sent.",
    ),
    action(
        "email_campaigns.set_campaign_html_content", "Set a campaign's content from custom HTML",
        "Store the HTML body of a draft campaign using the 'HTML custom code' editor. Best way for an agent to provide content, "
        "since it avoids the drag-and-drop editor. Other editors (drag-and-drop, simple text) and templates exist in the UI and were not captured.",
        obj({"id": {"type": "integer"}, "html": {"type": "string"},
             "storeOnlyText": {"type": "boolean", "default": False},
             "abVersion": {"type": ["string", "null"], "default": None},
             "templateLanguageVersion": {"type": "string", "default": "2"},
             "makeScreenshot": {"type": "boolean", "default": True, "description": "Generate the thumbnail."},
             "editorType": {"type": "string", "default": "4", "description": "'4' was the value for the HTML editor. Other values not mapped."},
             "userHash": {"type": "string", "description": "Per-user hash. Get it from email_campaigns.get_editor_account (field userHash). Do not log or store it."}},
            ["id", "html", "userHash"]),
        {"http": {"verb": "POST", "url": "https://editor-api.brevo.com/editor-api/campaign/{{id}}/store",
                  "body_template": {k: "{{%s}}" % k for k in (
                      "html", "storeOnlyText", "abVersion", "templateLanguageVersion", "makeScreenshot", "editorType", "userHash")}}},
        {"status": 200, "schema": obj({"html": {"type": "string"}, "text": {"type": "string", "description": "Plain-text version generated by the server."}})},
        preconditions=["A campaign draft exists.", "userHash obtained from email_campaigns.get_editor_account."],
        notes="Saved a minimal HTML body through the editor. A direct replay with a userHash taken from get_editor_account was not tested.",
    ),
    action(
        "email_campaigns.get_editor_account", "Get the email editor session (userHash)",
        "Return the per-user values the email editor needs, including userHash, which set_campaign_html_content requires. "
        "The response also holds a sessionId and the account phone number; never log, repeat or store them.",
        obj({}),
        {"http": {"verb": "GET", "url": "https://editor-api.brevo.com/editor-api/classic/account"}},
        {"status": 200, "schema": obj({"userHash": {"type": "string"}, "locale": {"type": "string"},
                                       "plan": {}, "features": {}, "permissions": {}})},
        how="replay",
        notes="Found by the blind-agent evaluation, which flagged userHash as a blocker. Keys seen: id, userHash, sessionId, locale, permissions, features, plan, pricingVersion, phoneNumber.",
    ),
    action(
        "contacts.check_duplicate_contact", "Find a contact id by email or phone",
        "Check whether a contact exists and get its id, using one identifier. Use after create_contact fails with duplicate_parameter, "
        "or before creating, to avoid the error. Works with the browser session only (no API key).",
        obj({"email": {"type": "string", "format": "email"}, "sms": {"type": "string"}, "whatsapp": {"type": "string"},
             "landline_number": {"type": "string"}, "ext_id": {"type": "string"}}),
        {"http": {"verb": "GET", "url": f"{CONTACTS}/contact/backend/contacts/is_duplicate_contact",
                  "query_params": ["email", "sms", "whatsapp", "landline_number", "ext_id"]}},
        {"status": 200, "schema": obj({"is_exist": {"type": "boolean"}, "contactId": {"type": ["integer", "null"]}})},
        how="replay",
        notes="Returned {is_exist: true, contactId: 2} for an existing email. Only the email parameter was tested.",
    ),
    action(
        "email_campaigns.schedule_campaign", "Schedule or send an email campaign",
        "Schedule or send a completed draft. Irreversible once emails go out: always confirm audience and content with the user first.",
        obj({"id": {"type": "integer"}}, ["id"]),
        {"method": "ui_only", "ui_steps": [
            "Open the draft in Marketing > Campaigns.",
            "Confirm Sender, Recipients, Subject and Design all show a green check.",
            "Click 'Schedule' and choose a time or send now."]},
        how="menu", destructive=True, reversible=False,
        side_effects=["Sends email to the selected recipients and consumes plan quota."],
        notes="Deliberately not executed: it would send real email, and the account shows a marketing-email suspension banner.",
    ),
    action(
        "email_campaigns.list_campaigns", "List email campaigns",
        "List email campaigns with id, name, status (draft, sent, ...), dates and subject. Use to find a campaign id or check a draft's state.",
        obj({"pageNumber": {"type": "integer", "default": 1}, "pageSize": {"type": "integer", "default": 20,
                                                                           "description": "Accepted; effect not verified."}},
            ["pageNumber"]),
        {"http": {"verb": "GET", "url": "https://email-campaigns-backend.brevo.com/email-campaign/api/campaigns",
                  "query_params": ["pageNumber", "pageSize"]}},
        {"status": 200, "schema": obj({"campaigns": {"type": "array", "items": obj({
            "id": {"type": "integer"}, "name": {"type": "string"}, "status": {"type": "string"},
            "subject": {"type": "string"}, "type": {"type": "string"}, "isAbTesting": {"type": "boolean"},
            "lastModifiedDate": {"type": "string"}, "sentDate": {"type": "string"}})}})},
        how="replay",
        notes="pageNumber is required: the server answers 400 'missing pageNumber parameter' otherwise.",
    ),
    action(
        "forms.create_form", "Create a sign-up form",
        "Create a subscription (sign-up) form that collects contacts. Free plan allows full-page/embedded forms; pop-up forms need the Professional plan. "
        "The UI also has Unsubscribe and Profile update form types, whose type values were not captured. The public API has no form endpoints.",
        obj({"name": {"type": "string"},
             "type": {"type": "string", "enum": ["subscription"], "default": "subscription",
                      "description": "Only 'subscription' was observed."},
             "enableGDPR": {"type": "boolean", "default": False}}, ["name"]),
        {"http": {"verb": "POST", "url": "https://forms-api.brevo.com/forms-api/forms",
                  "body_template": {"name": "{{name}}", "type": "{{type}}", "enableGDPR": "{{enableGDPR}}"}}},
        {"status": 201, "schema": obj({"id": {"type": "string", "description": "Form id (24-char hex string, not an integer)."},
                                       "name": {"type": "string"}, "numberOfContact": {"type": "integer"},
                                       "numberOfSubmits": {"type": "integer"}, "createdAt": {"type": "string"}})},
        side_effects=["Creates a form with a default 'Newsletter' design. The UI then opens the form designer; design edits were not captured."],
        notes="Created 'Catalogo teste formulario'.",
    ),
    action(
        "forms.list_forms", "List forms",
        "List forms with id, name, contact and submit counters.",
        obj({}),
        {"http": {"verb": "GET", "url": "https://forms-api.brevo.com/forms-api/forms"}},
        {"status": 200, "schema": obj({"forms": {"type": "array", "items": obj({
            "id": {"type": "string"}, "name": {"type": "string"},
            "numberOfContact": {"type": "integer"}, "numberOfSubmits": {"type": "integer"}})},
            "totalRecords": {"type": "integer"}})},
        how="replay",
        notes="Query parameters for the Sign-up / Unsubscribe / Profile update tabs were not explored.",
    ),
    action(
        "account.get_account_state", "Check account plan and sending readiness",
        "Return the plan and flags that decide whether sending works. Call before any send or activation flow: on the test account it "
        "reported plan FREE, transactional status 'phone_not_verified' and SMTP disabled. The response also contains the owner's personal "
        "details, which an agent should not repeat. It does NOT expose the marketing-email suspension shown as a banner in the UI, so a "
        "send can still be blocked when these flags look fine.",
        obj({}),
        {"http": {"verb": "GET", "url": "https://forms-api.brevo.com/forms-api/account"}},
        {"status": 200, "schema": obj({
            "organizationConfig": obj({"planTag": {"type": "string", "description": "e.g. FREE."}}),
            "isSMTPEnabled": {"type": "boolean"},
            "transactionalStatus": {"type": "string", "description": "e.g. phone_not_verified."},
            "isSenderAvailable": {"type": "boolean"}, "timezone": {"type": "string"},
            "defaultCountryCode": {"type": "string"}})},
        how="replay",
        notes="Served by the forms service but returns account-wide data. Other services expose similar account endpoints (account-management-backend, crm-backend-api plan-manager-info) that were not compared.",
    ),
    {**action(
        "contacts.create_list", "Create a contact list",
        "Create a static list of contacts inside a folder. Use for fixed audiences; for rule-based audiences use segments.create_segment.",
        obj({"name": {"type": "string", "maxLength": 255},
             "folder_id": {"type": "integer", "description": "Folder id. The default folder on a new account was 1."},
             "folder_name": {"type": "string", "description": "The folder's internal name, which can differ from the name shown in the UI "
                                                           "(folder 1 is shown as 'Your First Folder' but sent as 'Client_Folder')."},
             "is_folder": {"type": "boolean", "default": False}},
            ["name", "folder_id"]),
        {"http": {"verb": "POST", "url": "https://contacts-api-v2.brevo.com/lists/create",
                  "body_template": {"name": "{{name}}", "is_folder": "{{is_folder}}", "folder_id": "{{folder_id}}",
                                    "folder_name": "{{folder_name}}"}}},
        {"status": 201, "schema": obj({"id": {"type": "integer"}})},
        notes="Created 'Catalogo teste lista' (id 5). Whether folder_name is required was not tested.",
    ), "alternative_executions": [{"method": "public_api", "http": {
        "verb": "POST", "url": "https://api.brevo.com/v3/contacts/lists",
        "body_template": {"name": "{{name}}", "folderId": "{{folder_id}}"}},
        "auth": "API key in the api-key header. Not included here."}]},
    {**action(
        "contacts.get_lists", "List contact lists",
        "List contact lists with id, name, contact count and parent folder id. Use to find a list id before adding contacts or targeting a campaign.",
        obj({}),
        {"http": {"verb": "GET", "url": "https://contacts-api-v2.brevo.com/lists/get-lists"}},
        {"status": 200, "schema": obj({"data": {"type": "array", "items": obj({
            "id": {"type": "integer"}, "name": {"type": "string"}, "count": {"type": "integer"},
            "list_parent": {"type": "integer", "description": "Folder id."}, "entered": {"type": "string"},
            "isDynamicList": {"type": "integer"}})}})},
        how="replay",
        notes="A new account already has system lists ('Your first list', 'identified_contacts').",
    ), "alternative_executions": [{"method": "public_api", "http": {
        "verb": "GET", "url": "https://api.brevo.com/v3/contacts/lists", "query_params": ["limit", "offset", "sort"]},
        "auth": "API key in the api-key header. Not included here."}]},
    {**action(
        "contacts.add_contact_to_list", "Add contacts to a list",
        "Add one or more existing contacts to one or more lists. Asynchronous: success means the job was queued, so confirm with "
        "contacts.get_lists (count) before reporting it done. The same endpoint runs other bulk actions; only ADD_TO_LIST was verified.",
        obj({"ids": {"type": "array", "items": {"type": "integer"}, "description": "Contact ids."},
             "link_list_ids": {"type": "array", "items": {"type": "integer"}, "description": "Target list ids."},
             "action": {"type": "string", "enum": ["ADD_TO_LIST"], "default": "ADD_TO_LIST"},
             "is_all_selected": {"type": "boolean", "default": False,
                                 "description": "true applies to every contact matching fe_query instead of ids. Not tested."},
             "fe_query": {"type": "object", "default": {}}, "searchBy": {"type": "string", "default": ""}},
            ["ids", "link_list_ids"]),
        {"http": {"verb": "POST", "url": "https://contacts-api.brevo.com/contact/backend/actions/list",
                  "body_template": {"action": "{{action}}", "is_all_selected": "{{is_all_selected}}", "ids": "{{ids}}",
                                    "link_list_ids": "{{link_list_ids}}", "fe_query": "{{fe_query}}", "searchBy": "{{searchBy}}",
                                    "is_anonymous_selected": False, "is_conversation_anonymous_contact_selected": False,
                                    "is_wonderpush_anonymous_contact_selected": False, "sourceId": None, "sourceType": None}}},
        {"status": 200, "schema": obj({"message": {"const": "Process dispatched successfully"}})},
        side_effects=["Queues a background job; the list count updated within a few seconds in testing."],
        preconditions=["The contacts and lists exist (contacts.get_lists)."],
        notes="Added contact 2 to list 5 from the Contacts page bulk action; list count went from 0 to 1.",
    ), "errors": [
        {"when": "action is not a known bulk action", "status": 400,
         "response": {"message": "{\"action\":\"Invalid Action\"}"},
         "agent_should": "Use ADD_TO_LIST. The endpoint does not list valid values."}],
     "alternative_executions": [{"method": "public_api", "http": {
         "verb": "POST", "url": "https://api.brevo.com/v3/contacts/lists/{{listId}}/contacts/add"},
         "auth": "API key in the api-key header. Not included here."}]},
]


def main():
    for a in ACTIONS:
        category, slug = a["id"].split(".", 1)
        out = ROOT / "catalog" / category / f"{slug}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(a, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {len(ACTIONS)} curated actions")


if __name__ == "__main__":
    main()
