# Business Automation Portal (BAP) — add-on

No-code portal where **business users** run and manage integrations built by developers; white-labelable, so ISVs/SaaS partners embed it as their own product. Purchased separately via Frends Sales. Docs: `https://docs.frends.com/bap/` (subpages under `/bap/general/…`, `/bap/guides/…`, `/bap/release-notes/…` — release notes state required Frends version, e.g. BAP 1.0.3 requires Frends 6.2 and added Long-Running Process support; check the Frends Version Compatibility page).

## The tag-based model

Everything in BAP is wired through **Frends Tags**:

1. **Developer flow:** build and test a Process in Frends → move config to **Process Variables** (not `#env`) so users can fill them in → create a **Template** from it (Templates list) → give the Template tags. Template tags control which BAP Organizations see it in the **Integration Catalogue**.
2. **Business-user flow:** pick a Template from the catalogue → guided wizard fills Process Variables → **test run** in the org's Test Agent Group → deploy to the org's Production Agent Group → monitor executions (execution graph and details shown in BAP, without exposing the wider Tenant).
3. **Pre-created Processes:** alternatively tag an existing Process in Frends with a tag listed in the org's "viewable" tags; it must be **deployed to the Production Agent Group** (may take up to ~10 min to appear) and shows as **view-only** in "My Integrations".

## Organizations (the segregation unit)

Created either by public request from the login page (Portal Admin approves) or directly by a Portal Admin (Settings → Organizations → New organization). Settings per org:

- **Name** (unique), **Contact email** (becomes first org admin).
- **Domains to auto assign** — users with matching email domains auto-join.
- **Assign Tag to Processes created by Organization** — auto-tag for everything the org creates (governance/scoping).
- **Processes with Tag viewable by the Organization** — which existing Frends Processes appear (view-only).
- **Agent Groups: Test + Production** (required) — where the org's instances run.
- **Integrations available to Organization** — tag list controlling which Templates the org sees ("Configure" button).
- **Delete Organization** — removes org, its Processes and user associations, irreversibly.

## Roles, auth, configuration

- **Portal Administrator**: approves org requests, manages all orgs, whitelabeling, environment connections, auditing. **Organization admin/users**: invite-based onboarding within the org.
- Auth: invite-based accounts; optional **SSO** (separate configuration).
- **Shop Configuration** (Settings): enabling and configuring the catalogue/shop experience — which templates are offered and how.
- **Look & Feel**: logo, favicon, catalogue title/text, page-title prefix, landing-page text, custom CSS and extra `<head>` entries — full white-labeling.

BAP itself is updated by Frends automatically, in tandem with the iPaaS.
