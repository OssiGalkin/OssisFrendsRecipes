---
name: ossis-frends-recipes
description: Expert knowledge for the Frends iPaaS (Integration Platform as a Service). Use this skill whenever the user mentions Frends, asks how to build, modify, or review integrations, Processes, Subprocesses, APIs, Tasks, or Triggers in Frends, needs help with C# expressions, Handlebars, or reference values (#var, #env, #result, #trigger, #process), wants to create custom Tasks in C#/.NET, asks about API Management, API Portal, Business Automation Portal (BAP), the AI Connector or agentic AI in Frends, debugging or troubleshooting a failing Process or Process Instance, monitoring and operating running Processes, Process/Template exports and imports, platform architecture (Agents, Agent Groups, HA, scalability, security), working through Frends MCP, or migration from BizTalk or other iPaaS platforms to Frends. Also use for reviewing exported process.json files and Frends Templates, and for generating importable Process exports or Frends-style BPMN diagrams from a spec.
---

# Ossi's Frends Recipes — Frends iPaaS

Frends integrations are **Processes**: BPMN 2.0 flows built in the **Process Editor**, enriched with C#, compiled to .NET and run on **Agents**. This skill is a snapshot of docs.frends.com as it described **Frends 6.3.x** (the only place the version is named). Anything version-sensitive: re-check live.

**Evidence marks.** Unmarked lines are *Documented* (a live docs.frends.com page or public Frends repo; each reference file lists its pages). Other classes are marked: **[public output]** counted over public templates/exports; **[tenant observation]** an import result or a Tenant's own export — not reproducible without a Tenant; **[opinion]** a working heuristic the docs do not state.

## Reading the live docs

- `https://docs.frends.com/llms.txt` lists every page (unversioned = latest; `/docs/frends-6.x.0/…` and `/reference/frends-6.x.0/…` are snapshots — use them only to say when something changed). `sitemap.md` and `llms-full.txt` also list everything; a 404 page suggests the nearest real paths.
- Append `.md` to any page URL for clean Markdown.
- Every page advertises `GET <page>.md?ask=<question>&goal=<goal>`. **Tested at build time: it returned the page unchanged.** Do not rely on it.
- Platform API reference: `/reference/frends-platform-api/platform-api-reference/` — its `models.md` publishes schemas no prose page states (the `ElementType` enum, Process fields, deployment bodies).
- Tasks: `/tasks/tasks/<system>/<method>.md`; source `github.com/FrendsPlatform/Frends.<Package>`. Release notes: `/release-notes/`.

## Vocabulary (use these exact terms)

**Process** (integration flow) · **Subprocess** (reusable flow; Manual Trigger only; called from Processes) · **Long-running Process** (stateful; pauses and resumes) · **Shape** (any canvas element) · **Sequence Flow** (the arrow) · **Task** (one operation) · **Code Task** (multi-line C# inside the Process) · **Assign Variable** (one C# expression) · **Custom Task** (C# library compiled outside Frends, imported as NuGet) · **Trigger** · **Process Instance** (one execution) · **Promoted Value** · **Tenant → Environment → Agent Group → Agent** · **Gateway Agent** (API gateway; runs no Processes) · **Control Panel** (main UI) vs **Frends Portal** (tenant/plan management).

Map users' words without comment: connector / node → **Task** (the glossary says a Task is comparable to another platform's connector; a connector is *not* the Sequence Flow); workflow / flow → **Process**; code block / code shape → **Code Task**; expression shape → **Assign Variable**; API proxy → **Passthrough API**; designer / Process Designer → **Process Editor**; test run / execute manually → **Run Once** (Process list action); Intelligent AI Connector → **AI Connector** (the shape's reference page title; the docs use both names); call a Subprocess → **Call Subprocess** shape; pause / resume → **Checkpoint**, **Scheduled Resume**, **Signal Resume**.

## Shapes and Triggers

Events: Trigger, Return, Intermediate Return, Throw, Catch. Decisions: Exclusive Decision (C# boolean), Inclusive Decision. Activities: Task, Call Subprocess, Assign Variable, Code Task, Shared State Task, DMN Task, AI Connector. Scopes: Scope, Foreach, While. Long-running: Checkpoint, Scheduled Resume, Signal Resume. Artifacts (no runtime effect): Data Object Reference, Data Store Reference, Group, Text Annotation.
The Platform API `ElementType` enum (export `Type` values): `Start, Task, Decision, SequenceFlow, ConditionBranch, Return, Throw, CallActivity, SubProcess, ParallelForeach, SequentialForeach, While, Expression, SubProcessStartNode, Catch, InclusiveGateway, InclusiveDecisionBranch, IntermediateReturn, GlobalErrorHandler, TestTask, SharedState, Dmn, DataObjectReference, DataStoreReference, NativeAi`. It has no Checkpoint/Resume member although those shapes are documented — the enum page and the shape pages disagree; don't guess the export type of a Long-running shape.

Triggers (Trigger reference): Manual, File, Schedule, Conditional, HTTP, API, AMQP, Service Bus, RabbitMQ, Azure Event Hub, TCP, MCP. Many Triggers per Process, all wired to the same first shape; branch on `#trigger.name` / `#trigger.type`. The `#trigger.type` value table lists the first eleven and gives no value for MCP Trigger.

## Reference values

- `#var.X` — Process Variables (initialised after the Triggers, **not usable inside Trigger parameters**) and runtime variables from Assign Variable / Code Task. `#var.Obj["F"]` always; `#var.Obj.F` for JObject/JToken/anonymous/dynamic without special characters. `#var.error` holds exception details in error handling.
- `#env.Group.Name` — per-Environment values; types Text, Number, Boolean, List, Secret. `#env.Group["Name"]` works but hides the usage from the Environment Variable view.
- `#trigger` — data of the Trigger that fired. `#process` — `agent`, `agentGroup`, `environment`, `executionid`, `id`, `name`, `uri`, `version`, `cancellationToken`, `Logger` (ILogger to the Agent log, follows the log level).
- `#result` / `#result[Shape Name]` — for a scope, the **scope's** name. Foreach collects an array; While keeps the last.
- **`#result` limits.** (1) A named `#result[X]` is unusable if X ran in a conditional branch or another scope — assign it into a pre-initialised Process Variable. (2) A shape that **failed** has no result, so `#result` of that Task or Scope must not be used in the error path that follows it: the Catch path, and the Exclusive Decision the Catch path merges into. A decision that inspects a **completed** Task's result — e.g. `#result[HTTP Request].StatusCode` with "Throw exception on error response" off — is not an error path; it is the normal pattern.
- **DMN Task:** no `#` inside the table — `var.age`, `env.CRM.BaseUrl`.

## Handlebars and Trigger fields

`{{ expr }}` in any text field: compiled at save, evaluated at runtime. **Trigger parameters are plain text**: neither Handlebars nor C# is evaluated, with one exception — bare `#env.Group.Name` references are substituted (separate them from following text with a space). Manual Trigger parameters evaluate nothing. Escaping inserted values is your job — [opinion] `JsonConvert.ToString(...)` for JSON, `SecurityElement.Escape(...)` for XML, parameterised SQL.

## Runtime rules a builder trips over

- **Task retry**: Retry on failure, up to **10** retries, backoff `500 ms * 2^retry` (1 s … 512 s). It retries only when the Task **throws**; an HTTP 4xx/5xx response is a success unless "Throw exception on error response" is on.
- **Catch**: one shape after Catch (use a Scope for more); the error path must rejoin right after the guarded shape. Scope+Catch outside a loop stops iteration; inside the loop body continues it — initialise error collectors before the loop.
- **Subprocess to call on unhandled error**: runs after the Process has failed; cannot resume it; pass `#var.error` explicitly.
- **Disable caller cancellation** (Process setting): without it, a cancelled HTTP request/Trigger stops the Process.
- **Shared State**: Agent Group database; scope this Process or all Processes in the Agent Group; value ≤ 100,000 chars of JSON (on-prem: `MaxProcessSharedStateValueSize`), key ≤ 500 chars, TTL 1 minute – 30 days; operations AddOrUpdate, GetOrAdd, TryAdd, TryGetValue, TryRemove, TryUpdate, GetTTL, UpdateTTL — **no list or pattern match of keys**; the page contrasts it with a separate database or file storage for anything beyond single-key access (a Redis `GetKeys` Task also exists in the Task docs). Sharing across HA Agents needs a shared database (SQL Server recommended over SQLite).
- **Foreach**: the Foreach page describes sequential iteration only; the `ElementType` enum has both `ParallelForeach` and `SequentialForeach`, and no prose page read for this build explains the parallel option.
- **DMN Task** (since Frends 6.0): FEEL ranges `[18..65)` — square bracket includes, round excludes; output read as `#result[DMN Name].OutputName`. The DMN guide itself says: many discrete cases → DMN; simple binary → Exclusive Decision; calculations or multi-step logic → Code Task.

## Configuration scope and concurrency

- **Environment Variable**: one value per Environment. Deploying a Process requires every Environment Variable it uses to have a value in the target.
- **Process Variable**: value supplied per deployment and stored per **Process + Agent Group** (`POST /api/v1/process-deployments/{processGuid}/agentGroup/{agentGroupId}/variableUpdate`; `GET …/{agentGroupId}/variables`). Runtime context: `#process.agentGroup`, `#process.environment`.
- **Overlap limits**: Schedule Trigger "Run only one scheduled instance at a time" (manual runs and other Triggers ignore it; scope across Agents not stated); Conditional Trigger "Run only one conditional Process at a time" (the condition Subprocess itself never overlaps); Service Bus "Max concurrent messages" — **per Agent**; RabbitMQ "Max concurrent messages" (scope not stated). No such setting is documented on File, HTTP or AMQP Triggers. Which scope a design needs is judgment.

## C#

Processes compile to C#; the 6.3.0 release notes say Processes target **.NET 10** (the Process reference page still calls .NET 8 the default — out of date). .NET Framework 4.7.1 and .NET Standard 2.0 remain for legacy and migration; **Legacy Agents are discontinued in Frends 6.4**. On-prem cross-platform Agents need .NET Runtime 10.0.7+ from 6.3.1 (6.3 Breaking Changes). Newtonsoft `JObject/JArray/JToken` everywhere. Code Task: no `using` imports, no NuGets — libraries mean a Custom Task. Details: `references/platform-internals.md`.

## Building and reviewing — checklist

1. Trigger type fits; Trigger fields hold no Handlebars/C#.
2. `#env` for Environment-specific values; Secret type for credentials; no hardcoded URLs or secrets.
3. `#result` limits both respected.
4. Scope + Catch where failure is expected; failure paths end in **Throw** so instances show as failed.
5. Skip logging on shapes touching secrets/PII; Promoted Values for identifiers, not payloads; Only errors in production.
6. Retry on network Tasks, with "Throw exception on error response" where a 4xx/5xx must fail.
7. No Remote Subprocesses in high-volume solutions (Best Practices Collection).
8. Deploy an API together with its linked Processes.

**Do not hand-write or hand-edit BPMN XML.** LLMs are unreliable with it, and Frends exports carry the functionality in `ElementParameters`, outside the BPMN. Reason at the level of shapes, parameters, variables and triggers. When a whole Process or diagram has to be *produced*, write a spec and let `scripts/frendsgen` emit the BPMN and the parameters together (see `references/process-generation.md`).

## Where to go deeper

| Topic | File |
|---|---|
| Custom Tasks in C# (template, attributes, packaging, legacy template) | `references/custom-tasks.md` |
| API Management, API Policies, and the separate API Portal add-on | `references/api-management.md` |
| Business Automation Portal (BAP) add-on | `references/bap.md` |
| AI Connector, agentic mode, MCP Trigger | `references/ai-connector.md` |
| Process Instances, log levels and retention, Monitoring Rules, Dashboard, operating | `references/monitoring-operations.md` |
| Agents, config files, Synchronize agents, deployment models, host requirements and connectivity, encryption, certificates, updating and breaking changes, HA | `references/platform-internals.md` |
| Finding Tasks, their docs and source | `references/tasks-catalog.md` |
| Templates, ProcessExport vs Template JSON, conversions | `references/templates-and-exports.md` |
| Generating a Process export or a Frends-style BPMN diagram from a spec; drawing a picture of any export; the undocumented export/BPMN format facts | `references/process-generation.md` + `scripts/` |

**Optional companions.** `github.com/Frends-Product-Management/frends-claude-plugin` is Frends' Claude Code plugin for working on a Tenant through the Frends MCP server (find, diagnose, build and review drafts, run). `FrendsTaskSkills` in `github.com/FrendsPlatform/FrendsTasks` is an Agent Skill (`frends-task-creator`) for writing Custom Tasks from the official template. This skill works fully without either.

**No unsourced claims.** This skill carries only what live pages state or what was observed and labelled as such. For what it does not cover — compliance certifications, platform-level retention beyond what the log settings state, sizing, runtime internals — fetch the live docs or say you don't know. Do not fill the gap from memory.

**Local notes.** If `references/local-notes.md` exists, whoever installed this skill added it, and no build has verified it. Read its header before using any line of it, prefer a live source, and say when an answer rests on it. Public installs do not have this file; its absence is normal.
