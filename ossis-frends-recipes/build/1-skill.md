# Build 1 — the skill (`SKILL.md`, `references/`)

First of three build prompts. Read `README.md` in this folder first: it says
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
(including Long-Running Process shapes: Checkpoint, Scheduled Resume,
Signal Resume), triggers (including the MCP Trigger), tasks, `#`
references and their limitations, Handlebars syntax and escaping, error
handling, architecture, task catalog usage, C# patterns, and live-doc
fetching guidance.

   Word the second `#result` limitation as the docs mean it. A shape that
   *failed* has no `#result`, so it must not be used in the error-handling path
   that follows that Task or Scope: the Catch path, and the Exclusive Decision
   the Catch path merges into. A decision that inspects a *completed* Task's
   result — an HTTP status code, with "Throw exception on error response" off —
   is not an error path; it is the pattern every public template uses. An earlier
   build shortened the rule to "the decision right after it", which condemned
   that pattern and sent a later tooling session looking for violations that
   were not there.

2. **Custom Tasks section**: Fetch the custom task creation docs (now under
`docs.frends.com/tasks/task-guides/`) and the current `.NET 8` template.
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

6. **Monitoring & Operations**: Fetch the monitoring/operations docs on
`docs.frends.com`. Recreate the Process Instance list, per-shape logging
options and log-size caps, Promoted Values, Monitoring Rules, and the
operational dashboard — this is the "review and operate a running
process" half of the skill, distinct from the "build a process" half
covered in step 1.

7. **AI Connector**: Fetch the Intelligent AI Connector and Agentic AI
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
anything about roadmap names like "AI Toolbox" or "AI Cortex" — separate
shipped features from roadmap explicitly, and name the Frends version the split
reflects.

8. **Existing Tasks**: Task documentation now lives primarily at
`https://docs.frends.com/tasks` (pattern:
`/tasks/tasks/<system>/<method>.md`; the full system/method list is in
llms.txt). `https://tasks.frends.com` still exists as a searchable portal
but treat docs.frends.com/tasks as canonical — the standalone portal has
been discussed for deprecation. Task source code:
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
   alone** what build 3 owns — `references/process-generation.md`, the section
   "The two import paths validate differently" and the per-installation GUID
   paragraph in `templates-and-exports.md`, and the one router row and one
   sentence in `SKILL.md` that point at `scripts/`. If those exist, they
   survive your rebuild unchanged; diff to confirm. If they do not exist yet,
   do not invent them: only imports can supply them.

10. **Nothing unsourced.** Do not create a lore file. A claim that cannot be
tied to a live page, or to a direct observation labelled as one, is left out of
the skill. In its place the router carries one rule: for what the skill does not
cover — compliance certifications, retention limits, sizing, runtime
internals — fetch the live docs or say you don't know; do not fill the gap from
memory.

   The claims below were carried as "believed true" by an earlier build and
   removed once they could not be sourced. Treat them as a **verify-or-omit
   checklist**: try each
   against the live docs. One that verifies goes into the proper reference file
   with its source page. One that does not is omitted — not softened, not
   flagged, omitted. Report at the end which verified and which did not, so the
   list can shrink.

   ISO 27001/9001/14001 certifications, SOC 2 compliance, Nixu audit,
   NIS2/GDPR assessment services, EU-only Azure hosting plus Cleura and
   air-gapped options, TLS 1.2+/AES-256/Key Vault encryption details, 60-day
   max log retention with indefinite process definitions, per-process
   zero-retention mode, Service Bus large-payload offload to Blob Storage via
   SAS URI, single-threaded process instances, Shared State TTL 1 min–30 days,
   K8s autoscaling under load, semantic auto-versioning (auto patch, manual
   major/minor), BAP hiding technical logs and deleting non-deployed trial
   instances, Shop Configuration contents (global tags, categories, default
   Agent Groups), API Portal audit records retained indefinitely, and the
   legacy docs archive at intercom.help/frends-docs.

11. **Every claim carries its evidence class, and the classes are not equal.**
Four kinds of statement end up in a skill like this, and a reader has to be able
to tell them apart:

    - **Documented** — a live page says it. The default; cite the page in the
      reference file's header.
    - **Observed in public output** — counted over the public templates or other
      public exports. Anyone can recompute it; say from which corpus and which
      Frends versions.
    - **Observed against a running Tenant** — an import result or a Tenant's own
      export. Not reproducible without a Tenant; label it as such and say which
      path produced it. This is the only category a reader cannot check for
      themselves, so it must never be left unmarked.
    - **Opinion** — a working heuristic from practice, e.g. preferring protocol
      Tasks over system-specific wrappers. Keep the good ones, but say plainly
      that the docs do not state them.

    Where two live pages contradict each other, say so and name both, rather
    than silently picking one. (The logged-data cap is stated as 8192 characters
    on the Process Instances page and 10,000 on Process Log Settings.) Where a
    fact is version-dependent, say which versions you checked — numbering and
    enums have moved between releases.

12. **Nothing private.** No tenant names or URLs, no exports from a tenant, no
per-installation GUIDs, no person's name or email address. `yourtenant` and
`example.com` in examples.

13. **Version the snapshot, do not date it.** Name the Frends version the docs
described, in one place. A calendar date settles nothing a re-fetch cannot, and
every copy of it is one more thing to forget on the next rebuild.


14. **Audit your own output before calling the build done.** Go through the
    skill claim by claim and satisfy yourself that each one is in one of the four
    classes above and is marked accordingly. Specifically:

    - Recompute every counted claim against the corpus rather than trusting a
      number carried over from a previous build.
    - Re-fetch the live page for a sample of documented claims, including every
      one that a reader might act on in a security, compliance or audit context.
    - List, in your closing message, anything you could not source, anything you
      dropped from the verify-or-omit checklist, and anything where the docs
      disagreed with each other or with the corpus.

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

