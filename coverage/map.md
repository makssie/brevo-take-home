# Coverage map (phase 1)

Source: sidebar menu of app.brevo.com, free plan, captured 2026-11-02. Status: `todo` until actions are in `catalog/` and validated.

## Product areas

| Area | Screen | URL | Priority | Status |
|---|---|---|---|---|
| CRM | Contacts | /contact/list | 1 | partial |
| CRM | Lists | /contact/list-listing | 1 | todo |
| CRM | Segments | /contact/segment | 1 | partial |
| CRM | Companies | /companies | 3 | todo |
| CRM | Deals | /crm/deals | 3 | todo |
| CRM | Tasks | /tasks | 3 | todo |
| CRM | Custom objects | /objects | 4 | todo |
| Marketing | Campaigns | /campaigns/listing | 1 | partial |
| Marketing | Landing pages | (no direct link) | 4 | todo |
| Marketing | Forms | /contact/forms-app/subscription | 3 | partial |
| Marketing | Statistics | /marketing-reports/statistics | 4 | todo |
| Marketing | Templates | /templates/listing | 2 | todo |
| Automations | Automations | /automation/automations | 2 | partial |
| Transactional | Email: real time, statistics, logs | /transactional/email/* | 2 | todo |
| Transactional | SMS: real time, statistics, logs | /transactional/sms/* | 3 | todo |
| Conversations | Inbox | conversations-app.brevo.com | 4 | todo |
| Conversations | Phone | /phone/onboarding | 4 | todo |
| Conversations | Meetings | /meetings/offer/all | 4 | todo |
| Commerce | E-commerce | /ecommerce | 4 | todo |
| Commerce | Loyalty | /loyalty | 4 | todo |
| Library | Media | content-library.brevo.com | 3 | todo |
| Analytics | Conversions, Analytics studio | /conversions/listing, /analytics | 4 | todo |
| Settings | Not in the menu: account, senders, domains, API keys, webhooks, team | /settings/advanced | 2 | todo, still to explore |

## Architecture finding

The web app is not one backend. Each domain talks to its own service on its own host, observed from the Contacts screen:

- `contacts-api.brevo.com` (contacts, attributes, lists and segments)
- `segments-api.brevo.com` (segment queries and counts)
- `contact-service-api.brevo.com` (consent groups)
- `crm-backend-api.brevo.com` (plan and CRM info)
- `views-manager-service.brevo.com` (saved views)
- `sidebar-backend.brevo.com` (menu, credits)
- `conversations-app.brevo.com`, `events-management-http.brevo.com`, `onboarding-backend-api.brevo.com`

Consequence for the catalog: `execution.http.url` must carry the full host, and each area needs its own capture pass.

## Observations

- Free plan: 300 emails per day, 0 SMS credits, phone verification needed before the first send.
- The account has 1 contact (the owner).
- Passive reads (the page's own `performance` entries) list the hosts but not payloads. Payloads need a request capture while an action runs.

## Next

- Discover the internal API auth model (cookie session vs bearer) without recording any token values.
- Compare with the public API (`api.brevo.com/v3`) to decide which actions can use it.
