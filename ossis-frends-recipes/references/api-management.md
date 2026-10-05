# API Management (built-in) vs API Portal (add-on)

**Keep these two apart.** API Management ships with every Frends Tenant and is how you expose and secure a Process as an API. **API Portal** is a separately purchased add-on product for publishing those APIs to external developers as self-service API Products. Docs: `https://docs.frends.com/frends-development/api-management.md`, `https://docs.frends.com/reference/api-management/…`, guides under `/guides/api-management/`, add-on at `https://docs.frends.com/api-portal/` (subpages under `/api-portal/general/…`).

## Built-in API Management

Workflow: write/import an **OpenAPI specification** in the API editor → link a Process (with an **API Trigger**) to each endpoint operation → deploy the API to an Agent Group → secure it with an **API Policy** → observe in **API Monitoring**. Expose externally via an Agent on a public resource, or use a **Gateway Agent** to load-balance requests without executing Processes on it. Lightweight alternative: HTTP Trigger (no OpenAPI spec, but still governed by API Policies).

**Passthrough APIs** forward requests as-is to another backend URL — API proxying for brand/domain coherence with no Process in between.

### API Policies (the access-control layer)

Every externally reachable endpoint must be covered by a policy — **no implicit public access**. A policy = targeted endpoints + authentication identities + optional throttling + optional logging configuration. Managed at APIs → API Policies.

- **Endpoint targeting:** method (`GET`/`POST`/…/`ALL`) + path. Free-text paths allowed (needed for HTTP Trigger endpoints, which don't appear in the dropdown). Segment-based prefix matching, case-insensitive: `/api/v1/crm` matches `/api/v1/crm/customers` but not `/api/v1/crmadmin`. `{id}` placeholders match one segment. **Gotcha:** a trailing slash on a policy path can block more-specific sub-path definitions — remove trailing slashes. More exact path wins over shorter path; explicit method wins over `ALL` at the same path.
- **Identities** (multiple per policy = alternative auth methods on the same endpoint):
  - **API Key** — keys created in Administration → API Keys, Environment-scoped (can conflict across Agent Groups in the same Environment; use Private Applications instead in that case). Delivered via header or query parameter; per-identity throttling.
  - **OAuth** — external issuer configured in Administration → OAuth applications; bearer token in `Authorization`; optional claim rules (`Exists` / `Exact` / `Regex`, ANDed).
  - **Private Application** — OAuth where the issuer is the Frends Tenant itself (Administration → Private applications); not Environment-scoped; same claim rules. This is what the API Portal add-on uses under the hood.
  - **Public Access** — unauthenticated. Since **Frends 6.3**, public access can be combined with other identities in one policy (valid credentials authenticate; no credentials → public).
- **Evaluation order:** OAuth → API Key → Public. A parseable OAuth token is final (invalid claims → reject even if a valid API key is also present); an unparseable token falls through. A valid OAuth token sent against a policy with no OAuth configured can yield 403 even with a valid API key.
- One policy per method+path per Agent Group (overlaps rejected at save). Want multiple auth methods → multiple identities in ONE policy, not multiple policies.
- **Logging configuration** (per policy, per Agent Group): without one, no API connection logs are written. Fields: Identity (default), Query Params (truncated at 1000 chars), Request/Response Headers (auth headers excluded), Error Response Body, Request/Response Body (1/10/100 KB cap). IP logging: direct client IP, X-Forwarded-For first, X-Forwarded-For all, or disabled. Set verbose in dev, minimal in prod.

**API Monitoring** shows every connection to the Tenant — including unsolicited requests — filterable by operation, status code, method.

Auth guides exist for API keys, Basic auth, Private Applications, OAuth implicit flow, and OAuth client credentials under `/guides/api-management/`.

## API Portal add-on

Self-service developer portal (white-label-ready) for publishing Frends APIs as **API Products**. Obtained via Frends Sales; own docs space with own release notes and a Frends-version compatibility page.

- **Concepts:** API Products (bundles of API operations) in a catalog; **Organizations** group external users; Production vs **Sandbox** environments per product (sandbox typically auto-granted, production usually requires admin approval via "Request Product Access").
- **Roles:** **API Portal Administrator** (global: manage all orgs, tokens, delete orgs, create orgs directly; cannot "deactivate" an org — revoke tokens/products instead) and **Organization Administrator** (own org: invite/remove members, request product access, manage/rotate/revoke tokens, configure SSO). Regular users consume APIs and can belong to multiple orgs (switch in profile menu).
- **Token mechanics — the key integration detail:** when an org gets access, the Portal automatically creates a **Private Application** in your Frends Tenant (one per org) and issues a JWT per API Product containing an **`ApiProductId` claim**. Your job on the Frends side: create an API Policy with a Private Application identity and a claim rule on `ApiProductId` (claim name is case-sensitive!). `Exists` rule = accept all portal products with one policy; `Exact`/`Regex` for per-product control. Public access must be OFF. Issuer/audience/expiry are validated automatically. The Portal only ever creates Private Applications/tokens (via Platform API), never modifies or deletes your existing ones.
- Interactive Swagger-style testing in the browser with the token auto-injected; tokens per org+product (not interchangeable); revoke/refresh from org settings.
- **Audit Log & Security** and **Customizing your API Portal** (look & feel, emails, custom domains) have dedicated pages under `/api-portal/general/`; admin console covers users, roles, organizations, audit logs, and access-request approval.
