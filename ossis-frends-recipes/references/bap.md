# Business Automation Portal (BAP) — add-on

Built for Frends 6.3.x from: `/bap/general/organizations.md`, `/bap/general/users.md`, `/bap/general/shop-configuration.md`, `/reference/process-development/template`, and search excerpts of `/bap/general` (index), `/bap/release-notes/bap-version-1.0.1` and `bap-version-1.0.5`. Not read this run: Look & Feel, Single Sign-On, the BAP guides.

A separate, simplified no-code UI deployed alongside the main Frends UI, where business users discover Templates, configure them and run them in the connected Tenant; also usable as an embedded iPaaS by ISV/SaaS partners (BAP 1.0.1 notes, which required Frends 6.0.3+). **BAP 1.0.5 requires Frends 6.2 or newer**, adds Promoted Variables to BAP instance views and moves BAP to .NET 10.

## How content reaches BAP — Tags

- **Templates**: a Template's **Template tags** decide which Organizations see it in the **Integration Catalogue**. A business user picks it, fills the Process Variables in a guided wizard, runs a test execution in a test environment, then deploys to production; execution details show without exposing the wider Tenant (Template page). Hence: put configuration in **Process Variables** with defaults, not `#env`.
- **Existing Processes**: tag them with one of an Organization's "Processes with Tag viewable" tags; they **must already be deployed to a production Agent Group** and may take up to 10 minutes to appear.

## Organizations

The segregation unit. Created by a public request from the login page (a Portal Admin accepts or denies) or by a Portal Admin (Settings → Organizations → New organization). Fields: **Name** (unique), **Contact email** (first org admin), **Assign Tag to Processes created by Organization**, **Processes with Tag viewable by the Organization**, **Agent Groups: Test and Production** (required), **Integrations available to Organization** (tag list), **Delete Organization** (removes its Processes and user associations; irreversible).
"Domains to auto assign" was **discontinued in BAP 1.0.2** — now the SSO configuration's *Associated domains* and the invitation dialog's *Initial organization*. (The managing-section of the same page still lists the old field.)

## Roles

Exactly three: **Portal Admin** (independent of any organization; everything in Settings; the only role that configures template and process tags per org; created only by another Portal Admin from Users), **Organization Admin** (manages the org's users), **Organization User** (creates Processes from available Templates, sees the org's Processes). One user can belong to several organizations with a different role in each and switches organization from the profile menu.

## Shop Configuration (Portal Admin)

Template tags available to **all** organizations; **Categories** (groups of tags used as search filters); default **test and production Agent Groups** used when an org sets none.
