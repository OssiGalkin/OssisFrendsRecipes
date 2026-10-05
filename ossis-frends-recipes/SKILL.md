---
name: ossis-frends-recipes
description: Expert knowledge for the Frends iPaaS (Integration Platform as a Service). Use this skill whenever the user mentions Frends, asks how to build, modify, or review integrations, Processes, Subprocesses, APIs, Tasks, or Triggers in Frends, needs help with C# expressions, Handlebars, or reference values (#var, #env, #result, #trigger, #process), wants to create custom Tasks in C#/.NET 8, asks about API Management, API Portal, Business Automation Portal (BAP), the AI Connector or agentic AI in Frends, debugging or troubleshooting a failing Process or Process Instance, monitoring and operating running Processes, Process/Template exports and imports, platform architecture (Agents, Agent Groups, HA, scalability, security), or migration from BizTalk or other iPaaS platforms to Frends. Also use for reviewing exported process.json files and Frends Templates, and for generating importable Process exports or Frends-style BPMN diagrams from a spec.
---

# Ossi's Frends Recipes — Frends iPaaS

Frends is a European hybrid iPaaS built on .NET 8 and Azure. Integrations are built as **Processes**: visual BPMN 2.0 flows in the Process Editor, enriched with C# expressions, compiled to C# and executed on **Agents**. This skill makes you an effective Frends integration architect: you can design, build, modify, review, and operate Processes, APIs, and other integration solutions.

## Rule 1: Live docs first

Frends evolves fast (a new minor version roughly every quarter). This skill is a snapshot, built from live documentation at the Frends 6.3 stage. **For anything version-sensitive — UI locations, shipped features, model names, task parameters — verify against the live docs before answering confidently.** If you have no way to fetch, still answer from this skill, and say which parts are from the snapshot and should be checked against docs.frends.com. The docs are unusually agent-friendly:

- **Index of everything:** `https://docs.frends.com/llms.txt` — full page listing with one-line descriptions, including versioned snapshots (paths like `/frends-6.2.0/...`). Unversioned paths are always the **latest** version.
- **Markdown mode:** append `.md` to any docs page URL to get clean Markdown (e.g. `https://docs.frends.com/reference/process-development/reference-values.md`).
- **Ask API:** any docs page answers natural-language questions:
  `GET https://docs.frends.com/<page>.md?ask=<question>&goal=<endgoal>` — documented on every page as returning a direct answer plus source excerpts. **Unreliable:** it has worked, and it has repeatedly returned the page unchanged instead. Treat it as a bonus, not a step to rely on. A 404 page is useful in its own right: it suggests the nearest real paths, and `https://docs.frends.com/sitemap.md` and `llms-full.txt` are the reliable ways to find a page.
- **Platform API reference:** `https://docs.frends.com/reference/frends-platform-api/platform-api-reference/` — OpenAPI schemas for Processes, Process Templates, deployments and the rest. Worth reading even when not calling the API: the schemas name fields and enums (for example `ElementType`) that no prose page states.
- **Task docs** now live at `https://docs.frends.com/tasks/` (see `references/tasks-catalog.md`). The older `https://tasks.frends.com` portal still works for search.
- **Templates:** `https://templates.frends.com` and `https://github.com/FrendsPlatform/FrendsTemplates`.
- **Task source code:** `https://github.com/FrendsPlatform/Frends.<TaskPackage>` (e.g. `Frends.HTTP`, `Frends.File`).
- **Release notes:** `https://docs.frends.com/release-notes/` — check these before claiming a feature exists or doesn't.

## Core vocabulary

Use these terms exactly; Frends terminology differs from other platforms.

**Process** — the integration flow (a BPMN sequence of Tasks). **Subprocess** — reusable flow, inserted into Processes as a Task-like shape; only Manual Trigger; called from Processes. **Long-Running Process** — stateful orchestration that can dehydrate (Checkpoint) and resume later (Scheduled/Signal Resume), available since Frends 6.2. **Shape** — any element on the canvas. **Task** — a single operation; what other platforms call a "connector". A **Sequence Flow** is the connecting arrow (NOT a connector). **Custom Task** — user-written C# class library imported as NuGet. **Code Task** — multi-line C# written inside the Process Editor (different from Custom Task!). **Assign Variable** — single C# expression shape. **Trigger** — starting condition; a Process can have several. **Process Instance** — one execution. **Promoted Value** — value surfaced into the Process Instance list for search/filter/monitoring.

Execution environment: **Tenant** (yourtenant.frendsapp.com) → **Environments** (Dev/Test/Prod, each with its own Environment Variable values) → **Agent Groups** (set of Agents running the same Processes) → **Agents** (the .NET runtime, cloud PaaS or self-hosted/on-prem; Docker/Kubernetes supported). **Gateway Agent** — API-gateway Agent that load-balances API requests to executing Agents without running Processes itself. **HA configuration** — multiple Agents in one Agent Group sharing load (requires load balancer + shared database).

UI: **Frends Portal** (tenant management) vs **Control Panel** (the main UI: Process Editor, Process List, Process Instance List, Dashboard, Administration).

## Shapes and Triggers

**Event shapes:** Trigger, Return, Intermediate Return (respond and continue async), Throw, Catch.
**Decision shapes:** Exclusive Decision (if/else; expression must be C# boolean; True → "Yes" branch, anything else → default branch), Inclusive Decision (every True branch runs; optional default).
**Activity shapes:** Task, Call Subprocess, Assign Variable, Code Task, Shared State Task (temporary key-value storage shared between executions), DMN Task (decision tables; note: reference values there are written WITHOUT the `#`, e.g. `var.X`, `env.G.X`), AI Connector.
**Scope shapes:** Scope, Foreach, While. Return inside a scope sets the scope's `#result` (Foreach collects an array of iteration results; While keeps only the last).
**Long-Running Process shapes (6.2+):** Checkpoint (persist state and dehydrate), Scheduled Resume (wait until a time without consuming resources), Signal Resume (another Process resumes this one).
**Artifact shapes (documentation only, no runtime effect):** Data Object/Store Reference, Group, Text Annotation.

**Triggers:** Manual, Schedule, File, Conditional (poll with custom criteria, e.g. SFTP folder), HTTP (lightweight endpoint), API (binds a Process to an API Management endpoint), AMQP, Service Bus, RabbitMQ, Azure Event Hub, TCP, **MCP Trigger** (exposes a Process as an MCP Tool for agentic AI).

## Reference values (`#` references)

Dynamic data is accessed with hashtag references in expressions:

- `#var.Name` — Variables. Created either as **Process Variables** (defined in Process settings, initialized at start, usable right after Triggers but NOT inside Trigger parameters) or at runtime via Assign Variable / Code Task with "assign variable" enabled. Object fields: `#var.Obj["Field"]` always works; dot notation `#var.Obj.Field` works for JObject/JToken/dynamic/anonymous. Can be explicitly typed (string, JObject, List) or dynamic.
- `#var.error` — always available inside error-handling paths (Catch); holds message, type, stack trace.
- `#env.Group.Name` — Environment Variables: centrally managed, per-Environment values. Types: Text, Number, Boolean, List, Secret (encrypted, hidden in UI). Dynamic access `#env.Group["Name"]` works but breaks usage tracking in the Environment Variables view — avoid it.
- `#trigger` — data from the trigger that fired. With multiple triggers, branch on `#trigger.name` / `#trigger.type`. Structure depends on trigger type (see each trigger's reference page).
- `#result` — output of the previous shape; `#result[Shape Name]` for a specific shape. For scopes the name is the **Scope's** name, not the inner Return's. HTTP Request example: `#result[HTTP Request].Body`.
- `#process` — instance metadata (execution id etc.).

**Critical `#result` limitations (common review findings):**
1. A named `#result[X]` can only be used if X is guaranteed to have executed — NOT if X ran inside a conditional branch or inside another scope. Workaround: initialize a Process Variable before the branch/scope and assign the result into it inside.
2. A shape that **failed** has no `#result`. So it must NOT be used in the error-handling path that follows that Task or Scope — inside the Catch path, or in the Exclusive Decision that the Catch path merges into. It is safe again only after the flow is known to have succeeded; capture what you need into a variable beforehand. This is about Catch paths: a decision that inspects a *completed* Task's result (e.g. an HTTP status code, with "Throw exception on error response" off) is not an error path, and is the normal pattern in the public templates.

## Handlebars

`{{ }}` embeds a C# expression inside any text-based field (Text, JSON, XML, SQL types). Compiled and validated at Process save; values resolved at runtime. Implicit `ToString()` — equivalent to `$"{expr.ToString()}"` — so it's the idiomatic way to drop a single value into a text field instead of switching the field to Expression type.

- **Escaping is your job.** Raw insertion breaks structured formats. JSON: `{{JsonConvert.ToString(#var.X)}}` (emits its own quotes — omit them in the template). XML: `{{System.Security.SecurityElement.Escape(#var.X)}}`. SQL: prefer the Task's parameterized queries over string building.
- **Triggers don't evaluate Handlebars or C#.** Trigger parameter fields are plain text, with ONE exception: bare `#env.Group.Name` references (no braces) are substituted, e.g. File Trigger filter `FilePrefix_#env.Grp.FileName.csv`. Manual Trigger parameters evaluate nothing at all.
- Decision shape conditions are locked to C# boolean expressions; no Handlebars there.

## C# in Frends

.NET 8 / C# 12 in current versions (.NET Framework 4.7.1 and .NET Standard 2.0 supported for legacy). Everything flows as Newtonsoft JSON (`JObject`/`JArray`/`JToken`) — that library and `System`, `System.Linq`, `System.Collections.Generic`, `System.Xml.Linq`, `Newtonsoft.Json(.Linq)` etc. are available without namespace prefixes. Anything else in mscorlib needs the fully qualified name, e.g. `System.Text.Encoding.UTF8.GetString(bytes)`.

- **Code Task cannot import libraries.** No `using` directives for namespaces (only `using` for resource disposal), no external NuGets. Need a library → that's what Custom Tasks are for.
- Code Task with "assign variable" ON must `return` a value; OFF must not return (acts as void). One action per shape; keep expressions one-liner-ish, precompute before embedding in Handlebars.
- Each imported Task exposes its parameter classes, e.g. build `Frends.HTTP.Request.Definitions.Header[]` in a Code Task to feed dynamic headers into an HTTP Request Task. Tooltips/docs/GitHub source show the expected types.

## Error handling essentials

- **Task retry:** Advanced settings → Retry on failure, max 10 retries, exponential backoff `500 ms * 2^retry` (1 s, 2 s, 4 s … 512 s). HTTP Request also needs "Throw exception on error response" enabled if 4xx/5xx should trigger retries (a received response is otherwise a success).
- **Standard try/catch pattern:** Scope around the risky part → Catch attached to the Scope → one handler shape (usually another Scope) → error path must merge back immediately after the guarded shape, with no shapes in between.
- **Loops:** Scope+Catch OUTSIDE the loop = stop iteration on error; Scope+Catch INSIDE the loop body = handle and continue. Initialize error-collection variables before the loop or they won't survive it.
- **Subprocess to call on unhandled error** (Process settings): last-chance cleanup/reporting hook when the instance fails; cannot resume the Process. Common use: auto-create a support ticket. Rate-limit repeated alerts with Shared State Tasks.
- **Monitoring Rules** (Administration): fleet-level error detection over Promoted Values — e.g. alert if fewer than N instances with `OrderId` per hour, or if any `PROC-…-ERROR` value appears. Handles "the Process never ran" failures that per-instance handling can't. Per-Environment, with active-time windows; can email or trigger a Process.
- Finish failure paths with **Throw** (not Return) so instances show as failed for monitoring.

## Building and reviewing Processes — checklist

When creating or reviewing a Process, check:

1. **Trigger** — the right type for the job, and its parameter rules respected (no Handlebars, no C#).
2. **Configuration** — `#env` for anything environment-specific; never a hardcoded URL or credential; Secret type for secrets.
3. **`#result`** — both limitations above: only where the named shape is guaranteed to have run, and never in an error path.
4. **Error handling** — Scope + Catch per the patterns above; every failure path ends in Throw, not Return.
5. **Logging** — skip-logging on shapes touching secrets or PII; Promoted Values for business identifiers; "errors only" level in production.
6. **Retries** — on network-facing Tasks, with "Throw exception on error response" where 4xx/5xx must count as a failure.
7. **Code Tasks** — one action each, no giant code blobs.
8. **Reuse** — Subprocesses for anything used in more than one place.

**Do not hand-write or hand-edit BPMN XML.** LLMs are unreliable with it, and Frends exports carry the functionality in `ElementParameters`, outside the BPMN. Reason at the level of shapes, parameters, variables and triggers. When a whole Process or diagram has to be *produced*, write a spec and let `scripts/frendsgen` emit the BPMN and the parameters together (see `references/process-generation.md`).

## Where to go deeper

Read the matching reference file before answering in these areas:

| Topic | File |
|---|---|
| Writing Custom Tasks in C# (.NET 8 template, attributes, packaging, legacy template) | `references/custom-tasks.md` |
| Built-in API Management AND the separate API Portal add-on | `references/api-management.md` |
| Business Automation Portal (BAP) add-on | `references/bap.md` |
| AI Connector, agentic AI, MCP in Frends | `references/ai-connector.md` |
| Monitoring, Process Instances, log levels, operating a running platform | `references/monitoring-operations.md` |
| Architecture: technologies, HA, scalability, security, lifecycle/CI-CD | `references/platform-internals.md` |
| Finding existing Tasks, their docs and source code | `references/tasks-catalog.md` |
| Templates, ProcessExport JSON vs Template JSON, conversions | `references/templates-and-exports.md` |
| Generating a Process export or a Frends-style BPMN diagram from a spec; drawing a picture of any export; the undocumented export/BPMN format facts | `references/process-generation.md` + `scripts/` |

**No unsourced claims.** This skill carries only what was verified against live documentation or observed directly — in public Frends output, or in imports into a Tenant, and labelled as which. For anything it does not cover — compliance certifications, retention limits, sizing, runtime internals — fetch the live docs or say you don't know. Do not fill the gap from memory.
