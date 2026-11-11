# Build 1 — the skill (`SKILL.md`, `references/`)

First of four build prompts. Read `README.md` in this folder first: it says
which files this build owns, which it must leave alone, and what is pinned.


---

I want you to build a Frends skill. I want you to be able to answer how to
do integration work, and modify and review processes, APIs, and other
integration solutions.

Build it completely from live sources — do not copy an existing skill file.
Structure it as a short SKILL.md (core knowledge + router, about a hundred
lines) plus reference files loaded on demand. Each reference file opens with the
pages it was built from.

**Pinned, not yours to write:** the frontmatter `name` and `description` are
given in `README.md`. Copy them in unchanged. A regenerated description that
reads well but drops the word someone actually types is the most likely way for
a rebuild to quietly break the skill.

**How to fetch the docs (re-verify these mechanisms still work at build
time):** `docs.frends.com` is agent-friendly:
`https://docs.frends.com/llms.txt` is a full index of every page including
versioned snapshots (unversioned paths = latest); appending `.md` to any
page URL returns clean Markdown; and any page answers natural-language
questions via `GET <page>.md?ask=<question>&goal=<endgoal>`. Use llms.txt
first to map the site, then fetch pages in Markdown mode. Bake this
fetching guidance into the skill itself so it can keep itself current.

The `?ask=` mechanism in particular has been unreliable: it worked on one build
and returned the page unchanged on later attempts. Test it once, write into the
skill what actually happened, and do not recommend it on this prompt's say-so. Two things that did work every time: a 404 page suggests the
nearest real paths, and `sitemap.md` / `llms-full.txt` list everything.

**Recency.** Prefer unversioned paths; they track the current release. Use a
versioned snapshot (`/frends-6.x.x/...`) only to say when something changed,
and name the version. Material that is not on docs.frends.com or a FrendsPlatform
repo and is older than about two years is a lead, not a source. Older community
material (the `CommunityHiQ` repos and anything framed around them) is legacy:
cover it only where a step asks for it, and label it so.

**The Frends MCP server is not yours.** Keep two things apart. The MCP
*features of the platform* — the MCP Trigger that exposes a Process as a tool,
and the AI Connector calling MCP Tools — are platform mechanics and stay in
this build (steps 1 and 7). The *Frends MCP server* that an AI assistant
connects to in order to work on a tenant — its guides, its tools, its
conventions — belongs to build 4, which writes what the skill knows about it. Do not describe MCP guides or tools in this build, even if you have a
connection. You may use a connection to *check* a platform fact, but the claim
you write must still be sourced from docs or public output; if it can only be
sourced from the server, report it for build 4 instead of writing it.
Never point a reader at `references/mcp.md` unless that file exists in the
skill folder you were handed: it only appears once build 4 has run.

**Facts from practice.** `build/README.md` lists, under "Facts from
practice", things the docs do not state. Carry each one into `SKILL.md` where
it belongs, in plain text with no mark, next to the documented statement it
extends or corrects. If a live page now states one of them, write the
documented form instead. Never silently revert one to an older docs-only
wording.

**Read the Platform API reference too**, under
`/reference/frends-platform-api/platform-api-reference/`. Its OpenAPI schemas
state things no prose page does — the `ElementType` enum, the fields of a Process
and a Process Template, the import conflict modes. It is the most
under-read part of the docs for this skill's purposes.

The URLs below are hints, and a model recovers from a moved page. What it does
not recover from is a page it never knew to look for. So define *done* by
traversal: for each numbered step, every page llms.txt lists under that area has
been read or deliberately skipped, and the reference file says which.

1. **Core skill from live docs**: Fetch `docs.frends.com`, including
glossary/integration pages. Recreate vocabulary, core concepts, shapes
(including the Long-running Process shapes — take their names from the current
docs and the `ElementType` enum; earlier builds used names the platform may no
longer use, so map any older names you find), triggers (including the MCP
Trigger; take the full list of Trigger types from the Trigger reference, since
new types arrive in service releases), tasks, `#`
references and their limitations, Handlebars syntax and escaping, error
handling, architecture, task catalog usage, C# patterns, and live-doc
fetching guidance.

   **Use the current canonical names, and map the old ones.** Check what the
   docs call the editor, a manual test execution, suspending and resuming a
   Process, calling a Subprocess, and the AI Connector, and use exactly that.
   Then give a short mapping from words users bring from other platforms
   (connector, workflow, node, code block, API proxy) and from superseded Frends
   names to the current term, so the skill can correct them without comment.

   Word the second `#result` limitation as the docs mean it. A shape that
   *failed* has no `#result`, so it must not be used in the error-handling path
   that follows that Task or Scope: the Catch path, and the Exclusive Decision
   the Catch path merges into. A decision that inspects a *completed* Task's
   result — an HTTP status code, with "Throw exception on error response" off —
   is not an error path; it is the pattern every public template uses. An earlier
   build shortened the rule to "the decision right after it", which condemned
   that pattern and sent a later tooling session looking for violations that
   were not there.

   Cover configuration scope as the docs and the Platform API reference state
   it: what an Environment Variable varies by, what a Process Variable varies
   by — in particular whether its value is stored per Agent Group (the Process
   Deployments endpoints show this) — what deployment requires of the
   Environment Variables a Process uses, and the `#process` values that expose
   the runtime context. Cover trigger concurrency: every setting that limits
   overlapping runs, on which trigger types it exists, and its scope (whole
   Agent Group or per Agent). Write the mechanics only; which scope a design
   needs is judgment and stays out.

   Cover the runtime rules a builder trips over, each only as far as a page
   states it: Task retry (formula, maximum, whether error responses that do not
   throw are retried), parallel execution (whether Foreach can run in parallel),
   Shared State (scope, value and key limits, TTL, whether keys can be listed or
   matched by pattern), what happens when an HTTP or API caller disconnects, at
   which level log levels are set, and how long Process Instances are retained:
   the default and where it is set.

   For the DMN Task, cover what catches people: reference values inside the
   table are written without the `#` (`var.X`, `env.G.X`), the FEEL range syntax
   and its bracket semantics (`[18..65)`), and how the table's output is read
   back (`#result[Display Name].OutputName`). Name the Frends version DMN
   arrived in. Then say, as **opinion**, when a DMN table is the better choice
   than an Exclusive Decision or a Code Task — this skill states the mechanics;
   the choice between them is judgment, and one sentence of it is enough.

2. **Custom Tasks section**: Fetch the custom task creation docs (now under
`docs.frends.com/tasks/task-guides/`) and the current template. Write down the
target framework the template and the docs declare now, and for which Frends
versions; it has moved between releases, so do not carry a version over from an
earlier build or from this prompt.
Note: `FrendsPlatform/FrendsTaskTemplate` was archived in April 2026 and
the template moved into the monorepo at
`github.com/FrendsPlatform/FrendsTasks` (folder `FrendsTaskTemplate`) —
verify the current location at build time. Also cover the legacy template
(`CommunityHiQ/TaskTemplate`). Recreate scaffold commands, static method
structure, parameter-class conventions, attributes, XML docs,
`FrendsTaskMetadata.json` (verify its exact format from live docs — it has
been misremembered before), packaging/install steps, and clearly mark
legacy template guidance as maintenance-only.

3. **API Management vs API Portal add-on**: Fetch the built-in API
Management docs on `docs.frends.com` (OpenAPI-based API definitions, API
Policies incl. path-matching and auth evaluation order, supported auth
methods, Gateway Agent) — this ships with every tenant, no add-on
required. Separately, fetch `docs.frends.com/api-portal` subpages
(under `/api-portal/general/`) for the API Portal add-on. Recreate both,
keeping them clearly distinct: API Management is how you expose and secure
a process as an API; API Portal is a separate purchasable product for
publishing that API to external developers (concepts, roles, publishing
flow, token/auth mechanics incl. the `ApiProductId` claim and
auto-created Private Applications, audit log, white-labeling).

   For API Policies, look for each of these and write what a page states:
   the parts of a policy; whether overlapping method + path + Agent Group
   coverage is rejected at save; how paths match (prefix, segment boundaries,
   trailing slash) and which rule wins inside a policy (exact path, explicit
   method vs `ALL`); what each identity type is scoped to (Environment or Agent
   Group) and which can be combined in one policy; OAuth claim rules and the name
   claim shown in API Monitoring; whether the OpenAPI `securitySchemes` affects
   runtime security; what happens to an endpoint with no policy; whether HTTP
   Trigger endpoints are governed; what logging and throttling can be set and at
   which scope; and what the migration from the older access-policy model
   produces. How to *organise* policies is judgment and stays out.

4. **Business Automation Portal / BAP add-on**: Fetch `docs.frends.com/bap`
subpages. Recreate concepts, developer template-tagging flow,
business-user workflow, Organizations configuration, Shop Configuration,
auth, and roles. Check the BAP release notes for the required Frends
version compatibility.

5. **Platform internals**: Fetch live docs for technologies, high
availability, scalability, data encryption, and integration lifecycle.
Recreate technology stack, HA requirements, scaling axes, versioning, and
security. Avoid stale-prone sizing numbers unless directly sourced from
current official docs.

   Include the Agent itself as the docs describe it: the configuration files it
   reads, their precedence, which ones an install or update overwrites and where
   lasting changes go; the application-settings reference pages per version and
   the settings each version added; container and Kubernetes specifics (secret
   file location, deployment models, persistent paths); transport fallbacks when
   message-bus ports are blocked; what happens to messages that do not fit the
   message bus, and where they go; how an Agent's HTTPS certificate is
   configured on each platform, what an update does to that setting, and when
   the Agent asks callers for a client certificate; legacy versus cross-platform
   Agents and their target frameworks, host runtime requirements and supported
   host operating systems and versions; Agent Group settings; and
   the Synchronize Agents action — what it does, when it runs on its own, and
   when to use it. Name the version each setting or behaviour belongs to.

   Include deployment as the docs describe it: the deployment models (cloud,
   hybrid, on-premises variants), the Agent registration modes, the choice
   between deploying and deploying with Triggers activated, the difference
   between a Process being deployed and its Triggers being active, how a new
   version takes over from running instances of the old one, and rollback.

6. **Monitoring & Operations**: Fetch the monitoring/operations docs on
`docs.frends.com`. Recreate the Process Instance list, per-shape logging
options and log-size caps, Promoted Values, Monitoring Rules, and the
operational dashboard — this is the "review and operate a running
process" half of the skill, distinct from the "build a process" half
covered in step 1.

7. **AI Connector**: Fetch the AI Connector (earlier marketed as the "Intelligent
AI Connector"; use the name the docs use now) and Agentic AI
docs on `docs.frends.com` (this is the core reason for the skill, so don't
let it fall out as an implicit side effect of step 1). Recreate what it is
(a native BPMN task — AI as a step inside a process, not a controller of
it), the typical pattern (trigger → AI Connector → gateway routing on the
result), and the design intent (every AI action logged as part of the
execution trace, human approval checkpoints as ordinary process shapes).
State of play at the 6.3 stage: the agentic mode (reasoning loop + MCP
Tools, formerly roadmap-named "AI Connector v2") SHIPPED in Frends 6.3;
MCP works in both directions (MCP Trigger exposes processes as tools).
Check `docs.frends.com/release-notes/` at build time before claiming
anything about roadmap names like "AI Toolbox" — separate
shipped features from roadmap explicitly, and name the Frends version the split
reflects.

8. **Existing Tasks**: Task documentation now lives primarily at
`https://docs.frends.com/tasks` (pattern:
`/tasks/tasks/<system>/<method>.md`; the full system/method list is in
llms.txt). Get Task information from docs.frends.com/tasks, not from
`https://tasks.frends.com`. Task source code:
`https://github.com/FrendsPlatform/Frends.<Package>`. Teach the skill how
to fetch relevant task information — docs and sources — when needed. You
might not always need the latest version; note that existing processes pin
imported task versions and upgrades are reviewable changes.

9. **Processes and Templates**: After the previous steps, learn how
Frends processes are actually made. Fetch `https://templates.frends.com/`
and `https://github.com/FrendsPlatform/FrendsTemplates/tree/main/Templates`.
Use the Appendix below to understand the difference between a Process
export and a Template export. The appendix was built by importing public
templates into a Frends tenant, creating processes from them, and
comparing the resulting process export against the original template — not
from private/tenant-only documentation. Use it to verify that what you've
learned from the public template repo holds true in practice. Be
especially mindful of parameters and how variables and references are used
in a process. Do not focus on BPMN XML too much — it is not something LLMs
are good at.

   That last sentence is about *you* and about anyone using the skill by hand.
   Producing BPMN and whole exports is the job of the tooling under `scripts/`,
   built by prompts 2 and 3. In this build: write
   `references/templates-and-exports.md` from the Appendix and the docs; tell
   the reader not to hand-write or hand-edit the `Bpmn` field; and **leave
   alone** what builds 3 and 4 own and what is pinned — `references/process-generation.md`,
   the section "The two import paths validate differently" and the
   task-GUID paragraph in `templates-and-exports.md`, the one router
   row and one sentence in `SKILL.md` that point at `scripts/`,
   `references/mcp.md` and the MCP block and router row in `SKILL.md`, and the
   pinned local-notes sentence. If those exist, they survive your rebuild unchanged;
   diff to confirm. If they do not exist yet, do not invent them: only imports
   and an MCP connection can supply them.

   Also write into this file, near the top: a Process export contains an
   organisation's integration logic and sometimes business data, so the reader
   must confirm they are allowed to give one to an AI before pasting or
   uploading it.

10. **Platform best practices**: Fetch the Best Practices Collection
(`/guides/general/frends-best-practices-collection.md`) and every guide it links
to, plus the Integration Security guidance. Put the Frends-specific
recommendations into the reference file they belong to — logging levels and
identifiers-not-payloads in monitoring, credentials in Secret Environment
Variables and the skip-logging option in the security part, Remote
Subprocesses at volume in platform internals, deploying an API together with its
linked Processes in API management — each with its page. Do not create a
best-practices file that repeats them, and do not restate general integration
advice the page gives (design before building, retry only transient errors):
that belongs to an architecture skill, not to this one. The test for every
line: would it be wrong on a platform other than Frends? If not, leave it out.
Extend the router's build/review checklist only with items the page supports.

11. **Nothing unsourced.** A claim that cannot be tied to a live page, or to a
direct observation labelled as one, is left out of the skill. In its place the
router carries one rule: for what the skill does not cover — compliance
certifications, platform-level retention beyond what the log settings state,
sizing, runtime internals — fetch the live
docs or say you don't know; do not fill the gap from memory. Directly after that
rule, copy the pinned local-notes sentence from `README.md` verbatim. Do not
create the file it mentions, and do not read it as a source if one is installed.

12. **Every claim carries its evidence class, and the classes are not equal.**
The classes are defined in `README.md`. Four of them end up in what this build
writes — *Served by MCP* is build 4's — and a reader has to be able to tell the
marked ones apart:

    - **Documented** — a live page says it. The default; cite the page in the
      reference file's header.
    - **Observed in public output** — counted over the public templates or other
      public exports. Anyone can recompute it; say from which corpus and which
      Frends versions.
    - **Practice** — how Frends behaves where the docs are silent (the "Facts
      from practice" list). State it plainly, unmarked, as how it works.
    - **Opinion** — a working heuristic from practice, e.g. preferring protocol
      Tasks over system-specific wrappers. Keep the good ones, but say plainly
      that the docs do not state them.

    Where two live pages contradict each other, say so and name both, rather
    than silently picking one. (The logged-data cap is stated as 8192 characters
    on the Process Instances page and 10,000 on Process Log Settings.) Before
    calling two pages contradictory, check whether they describe different
    scopes or different versions. For example, a guide saying public access
    replaces the other authentication methods describes one identity, while the
    API Policies reference describes several identities in one policy, which
    can be combined from 6.3; both can be true. Where a fact is
    version-dependent, say which versions you checked — numbering, enums and
    defaults have moved between releases. The default Process target framework
    is one: say which version made the current default the default, and treat a
    page that still names an older default as out of date, not as a second
    truth.

13. **Nothing private.** No tenant names or URLs, no exports from a tenant, no
tenant GUIDs, no person's name or email address. `yourtenant` and
`example.com` in examples.

14. **Version the snapshot, do not date it.** Name the Frends version the docs
described, in one place. A calendar date settles nothing a re-fetch cannot, and
every copy of it is one more thing to forget on the next rebuild.


15. **Audit your own output before calling the build done.** Go through the
    skill claim by claim and satisfy yourself that each one is in one of the four
    classes above and is marked accordingly. Specifically:

    - Recompute every counted claim against the corpus rather than trusting a
      number carried over from a previous build.
    - Re-fetch the live page for a sample of documented claims, including every
      one that a reader might act on in a security, compliance or audit context.
    - List, in your closing message, anything you could not source, and
      anything where the docs disagreed with each other or with the corpus.

    - Run the scenarios in `scenarios.md` marked for build 1, as the skill's
      user with only `SKILL.md` and `references/` open and **no MCP
      connection**, and report pass/fail per scenario. A failure is fixed in the
      skill, not in the scenario.

    An earlier build asserted that the docs never state the shape `Type`
    numbering. They do — the Platform API reference publishes the `ElementType`
    enum. That went unnoticed through several sessions because nobody went
    looking for a public source for something already believed to be private
    knowledge. Assume there is a page you have not read.

---

## Appendix: Key JSON difference: Template vs ProcessExport

*(Derived by importing a public template from `templates.frends.com`
into a Frends tenant, creating a process from it, and diffing
the resulting process export against the original template JSON
— not from private documentation.)*

### Normal ProcessExport JSON

Your local exports use this shape:

```json
{
  "Processes": [ { "... process ..." } ],
  "LinkedTasks": {
    "<process-guid>": [ "... task package refs ..." ]
  },
  "LinkedSubProcess": {
    "<process-guid>": [ "... subprocess refs ..." ]
  },
  "Version": "Acc41"
}
```

A single export file can contain many processes.

### Public Template JSON

Public template `process.json` files use:

```json
{
  "ProcessTemplates": [
    {
      "Name": "...",
      "Modified": "...",
      "Modifier": "...",
      "Tags": [],
      "TemplateProcessTags": [],
      "Description": "...",
      "Version": 1,
      "UniqueIdentifier": "<template-guid>",
      "ProcessVariablesJson": "{...}",
      "ProcessInfo": {
        "Process": { "... same 29 process fields as ProcessExport process ..." },
        "LinkedTasks": {
          "<inner-process-guid>": [ "... task package refs ..." ]
        },
        "LinkedSubProcess": {},
        "Version": "Acc41"
      }
    }
  ]
}
```

So a template is essentially:

> template metadata wrapper + one embedded process export object

The embedded `ProcessInfo.Process` has the same core fields as a
process export process:
`Name`, `UniqueIdentifier`, `Bpmn`, `ElementParameters`, `TriggersJson`,
`UsedTasksJson`, `RequiredEnvironmentVariables`, etc.

## Important semantic difference: variables

Public templates are built for portability:

- They use `#var.*` for configuration.
- They have `RequiredEnvironmentVariables: []`.
- Their configurable values are stored in outer `ProcessVariablesJson`.

Your local process exports mostly use tenant-specific environment
variables:

- Many references to `#env.*`
- Populated `RequiredEnvironmentVariables`
- Usually `ProcessVariablesJson: null`

That is the biggest practical difference.

For a portable template, move tenant-specific settings from
`#env.Some.Variable` to Process Variables like
`#var.ApiBaseUrl`, `#var.Username`, etc. This avoids requiring the target
tenant to already have the same Environment Variables.

## Creating a Process from a Template

Official/safest flow:

1. Frends Control Panel → **Templates**
2. **Import from file**
3. Select template `process.json`
4. **Create Process from Template**
5. Fill Process Variables
6. Save/edit/deploy as normal

Via Platform API after template exists in tenant:

```http
POST /api/v1/process-templates/{templateId}/create-process
```

Body:

```json
{
  "name": "My Process",
  "description": "Created from template",
  "ignoreProcessTags": false,
  "processVariables": [
    {
      "name": "ApiKey",
      "value": "\"secret-or-env-reference\"",
      "isSecret": true,
      "mode": "text",
      "description": "API key"
    }
  ]
}
```

## Converting Template JSON to ProcessExport JSON

Mechanically:

```text
ProcessTemplates[0].ProcessInfo.Process -> Processes[0]

ProcessTemplates[0].ProcessInfo.LinkedTasks -> LinkedTasks

ProcessTemplates[0].ProcessInfo.LinkedSubProcess -> LinkedSubProcess

ProcessTemplates[0].ProcessInfo.Version -> Version
```

Recommended extra step:

```text
If outer ProcessVariablesJson exists, copy it to Processes[0].ProcessVariablesJson
```

Otherwise a raw process import may lose the template's variables.

Pseudo-structure:

```json
{
  "Processes": [
    "<ProcessTemplates[0].ProcessInfo.Process>"
  ],
  "LinkedTasks": "<ProcessTemplates[0].ProcessInfo.LinkedTasks>",
  "LinkedSubProcess": "<ProcessTemplates[0].ProcessInfo.LinkedSubProcess>",
  "Version": "Acc41"
}
```

Caveat: if importing into the same tenant, duplicate `UniqueIdentifier`
values may collide. If regenerating the process GUID manually, also
re-key `LinkedTasks` /`LinkedSubProcess` from old GUID to new GUID.

**This conversion is not sufficient on its own.** Later import testing showed
the Process import path rejects values the Template path accepts (`GraphJson`,
`Modifier`, GUID casing in `UsedTasksJson`), and that task GUIDs differ per
installation. Those findings are build 3's section of
`templates-and-exports.md`; point at it from here, do not restate it.

## Converting ProcessExport JSON to Template JSON

Mechanically wrap one selected process:

```text
Processes[i] -> ProcessTemplates[0].ProcessInfo.Process

LinkedTasks[guid] -> ProcessTemplates[0].ProcessInfo.LinkedTasks[guid]

LinkedSubProcess[guid] -> ProcessTemplates[0].ProcessInfo.LinkedSubProcess[guid]

Version -> ProcessTemplates[0].ProcessInfo.Version
```

Add template metadata:

```json
{
  "ProcessTemplates": [
    {
      "Name": "Template name",
      "Modified": "...",
      "Modifier": "...",
      "Tags": ["Template category tags"],
      "TemplateProcessTags": ["Tags for created processes"],
      "Description": "...",
      "Version": 1,
      "UniqueIdentifier": "<new-template-guid>",
      "ProcessVariablesJson": "{...}",
      "ProcessInfo": {
        "Process": { "... process ..." },
        "LinkedTasks": {},
        "LinkedSubProcess": {},
        "Version": "Acc41"
      }
    }
  ]
}
```

But for a good reusable template, do not just wrap a production process
as-is. First replace tenant-specific `#env.*` settings with Process
Variables and populate `ProcessVariablesJson`.

