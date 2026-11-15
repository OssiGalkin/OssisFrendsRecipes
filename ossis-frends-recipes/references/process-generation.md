# Generating Processes and diagrams

`scripts/frendsgen` is one Python package with two entry points that share one layout engine:

| You want | Use | Output | Can Frends import it? |
|---|---|---|---|
| A working Process from a spec | `python3 -m frendsgen generate spec.yaml -o process.json` | ProcessExport | Yes, within the scope below |
| A picture of a design — for a spec, review, blog post | `python3 -m frendsdiagram.generate spec.json out.bpmn` | `.bpmn` with full layout | **No.** A diagram has no `ElementParameters`, so no functionality |
| A picture of an existing export | `python3 -m frendsgen picture export.json -o out/` | SVG drawn from the file's own layout | n/a |
| An editable spec from an existing export | `python3 -m frendsgen lift export.json --spec -o my.yaml` | YAML | n/a |

Run everything from `scripts/` (a read-only skill directory is fine; write outputs elsewhere with `-o`). `generate`, `validate` and `lift` need only Python 3, plus PyYAML for YAML specs (JSON specs work without it). `picture` and the `diagram` validate/render/extract tools also need `lxml`. Full usage, tests and architecture: `references/generator/README.md`.

**"Make me a Frends process" usually means a picture.** Ask which one is wanted when it is not obvious. The two scopes differ on purpose: a wrong picture costs nothing, a wrong `ElementParameters` entry is a failed import.

## Scope

**Importable export (`generate`), legacy form** (the default) — Manual Trigger; `Frends.HTTP.Request`; Assign Variable; Code Task; Exclusive Decision whose branches terminate or merge back to the step after the decision; Foreach; While; Return; Throw; Process Variables.

**Importable export, `target: "6.3"`** — everything above plus every other documented shape and all twelve Triggers: Scope; Catch; Intermediate Return; Call Subprocess; Subprocess to call on unhandled error; Inclusive Decision; Shared State `AddOrUpdate`; DMN Task; AI Connector; Checkpoint; Signal Resume; the Checkpoint / Scheduled Resume wait loop; several Triggers on one Process; Manual Trigger parameters. Each is rebuilt field for field from a reference export made in the Frends 6.3.2 Process Editor (`assets/fixtures/`), and lifting that export and regenerating it reproduces every shape entry by Id. Four constructs are not in the export and follow the fixtures README's description instead: Catch on a Call Subprocess, the unhandled-error Subprocess, the Scheduled Resume loop and the Service Bus Trigger. The queue and hub Triggers need real connection settings (broker address, connection string) before they activate.

Still refused by name: other Tasks (their parameter schemas need real instances), other Shared State operations, `#env` closure, promoted values, artifacts in an importable file, arbitrary graphs. HTTP Request is the one in the public templates, with its parameter set and GUID.

**Diagram only (`diagram.generate`)** — the full vocabulary: `trigger`, `scope_trigger`, `task`, `assign_variable`, `code_task`, `shared_state_task`, `call_subprocess`, `dmn_task`, `ai_connector`, `decision`, `inclusive_decision`, `return`, `throw`, `intermediate_return`, `scope`, `foreach`, `while`, `catch`, `checkpoint`, `signal_resume`, `scheduled_resume`; plus `artifacts` (`text_annotation`, `data_object_reference`, `data_store_reference`, `group`) and a per-node `color`. Arbitrary flow graphs, cycles included.

## Spec format (importable Process)

YAML or JSON. `assets/examples/order-sync.yaml` uses every construct; `lift --spec` writes this format from any real export that fits, which is the fastest way to see a construct you care about. Unknown keys are errors, never silently dropped.

```yaml
name: Order sync                       # required
description: ...
modifier: you@example.com              # any non-null string
trigger: manual                        # legacy form: Manual only; see 6.3 additions
variables:                             # Process Variables; value is JSON, not C#
  - {name: ShopBaseUrl, value: '"https://shop.example.com/api"', description: ...}
  - {name: ShopToken,   value: '""', secret: true}
  - {name: Retries,     value: '3'}       # JSON: `[]` loads as a fixed-size System.Array (no .Add);
                                         # build lists in an `assign: ... new JArray()` step instead
steps:
  - assign: {variable: orders, expression: {csharp: "new JArray()"}}
  - task:
      type: http_request               # the only Task with a parameter schema
      params: {method: GET, url: {csharp: "#var.pageUrl"}, authentication: OAuth,
               token: {csharp: "#var.ShopToken"}}
    name: Get orders                   # name/description/no_log/retry sit beside the step key
    retry: 3                           # 1-10
  - decision:
      name: Fetched?
      condition: {csharp: "#result[Get orders].StatusCode == 200"}
      then: []                         # empty or omitted => continue with the next step
      else:
        - throw: {message: "Shop API returned {{#result[Get orders].StatusCode}}"}
  - foreach: {name: For each order, item: order, in: {csharp: "#result[Get orders].Body"}, do: [...]}
  - while:   {name: Pages, condition: {csharp: "#var.pageUrl != null"}, max_iterations: 500, do: [...]}
  - code:
      variable: pageUrl                # omit => void Code Task
      statement_mode: true
      expression: {csharp: "{ ... return x; }"}
  - return: {csharp: "#result"}
```

- An expression is a bare string (the field's default mode), `{<mode>: value}`, or `{mode:, value:}`. Modes: `text`, `csharp`, `select`, `toggle`, `integer`, `json`, `xml`, `sql`. Defaults: `csharp` everywhere except a Throw `message`, which is `text` (so Handlebars work in it).
- A decision branch that does not end in `return`/`throw` merges back to the step after the decision, whether it is empty or holds steps. Merging anywhere else is not expressible.
- A sequence that does not end in `return`/`throw` gets a `return: #result` appended. Container bodies get their inner start event automatically.
- `http_request` params: `method`, `url`, `message`, `result_method`, `headers: [{name, value}]`, `authentication`, `username`, `password`, `token`, `timeout_seconds`, `follow_redirects`, `throw_on_error`, `allow_invalid_certificate`, `allow_invalid_charset`, `automatic_cookie_handling`, and the `certificate_*` fields (`tasks.py`).
- Pin `unique_identifier` only when you mean to overwrite that Process; otherwise every run gets a new GUID.

### 6.3 additions (`target: "6.3"`; `assets/examples/all-shapes-6.3.yaml` uses every one)

```yaml
target: "6.3"
triggers:                                # or `trigger:`; all wire to the first step
  - {type: manual, parameters: [{name: OrderId, default: "42"}, {name: Key, secret: true}]}
  - {type: service_bus, config: {queueName: orders, connectionString: "#env.Bus.Conn"}}
subprocesses: [{name: Notify, guid: ..., parameters: [input]}]   # or --subprocesses-from
on_unhandled_error: {subprocess: Notify, params: {input: "failed"}}
preserve_references_at_checkpoint: true
steps:
  - assign: {variable: total, expression: "0"}
    respond_early: {csharp: '"accepted"'}           # Intermediate Return
  - task: {...}
    on_error: {variable: error, do: {throw: {message: "..."}}}   # Catch: exactly one shape
  - scope: {name: Book, do: [...]}                  # Catch-able
  - call: {subprocess: Notify, params: {input: {csharp: "#var.x"}}}
  - inclusive: {name: Routes, branches: [{name: Big, condition: "...", do: [...]}],
                default: {name: Default}}
  - dmn: {inputs: [{expression: var.total, type: integer}], output: Category,
          rules: [{when: ["<5"], then: '"Low"'}]}
  - shared_state: {operation: AddOrUpdate, key: k, value: {csharp: "#var.x"}, ttl: 2}
  - ai_connector: {params: {...from lift --spec...}, user_prompt: "...", model: "..."}
  - wait_until: {checkpoint: {name: Wait}, condition: "...", every_minutes: 60, max_iterations: 24}
  - checkpoint: {name: Before signal}
  - signal_resume: {}
```

- Trigger types: `manual http api file schedule conditional mcp tcp event_hub rabbitmq amqp service_bus`. `config` overrides the editor's defaults; unknown keys are errors. Trigger fields refuse Handlebars and `#var`/`#result`/`#trigger`/`#process`; a credential field (connection string, password, key, secret) takes only a bare `#env.Group.Name`.
- An `api` Trigger needs `openApiDocument` (the API's OpenAPI document as text), `basePath` (its server URL, starting `/api/`) and `routeTemplate` (base path without the leading slash, plus one path in the document), with `httpMethod` matching an operation there. The document cannot be empty. Linking the Process to the API is not part of the Process file: after importing the API (from the same document) and the Process, link them in API Management with *Link Process*, or through the Frends MCP server.
- A Conditional Trigger names its condition Subprocess with `subprocess: <name>`, bound like any Subprocess; a literal `processGuid` is refused. Frends lists it in `UsedSubprocessesJson` and `LinkedSubProcess` like a called Subprocess, and so does the generator. Import the condition Subprocess first: until it exists, the editor shows it as missing and Frends refuses to export the Process. A Schedule Trigger without `seasonStartDate` gets the generation date.
- A Catch's handler is exactly one shape: not a `decision`, `inclusive` or `wait_until` (they expand to several), not a shape with its own `on_error`/`respond_early`, and never a `throw` or `return` — Frends 6.3.2 refuses that import. To fail after a Catch, store `#var.error` in a Process Variable and Throw after the rejoin (`assets/examples/all-shapes-6.3.yaml`). Use a `scope` as the handler for more.
- A statement-mode `code` step without `variable` must not `return` a value (CS8030 on import); with `variable` it must `return` one. The generator refuses both mistakes.
- A Catch guards a Task, Scope or Call Subprocess only (not a Foreach or While — wrap those in a Scope). Its one handler shape rejoins at the guarded shape's successor or terminates. One shape cannot carry both `on_error` and `respond_early`: the Task reference allows one or the other.
- DMN: no `#` in the table. Outputs read as `#result[<name>].<output>`. A lifted table is carried verbatim.
- `subprocess: true` makes the file a Subprocess (`IsSubprocess`): one Manual Trigger, whose `parameters` are what callers pass, and its Return is the call's result. Generate it first, then the caller with `--subprocesses-from <the Subprocess's export>`: a Subprocess in that file is bound by name, with its own GUID and parameters. Import the Subprocess first; a new one keeps the GUID in the file, which is what the caller binds to. Re-importing it later, Frends asks whether to make a new version of the existing Process or a new Process; choose the new version, or callers lose it. The caller's `LinkedSubProcess` entry repeats the Subprocess's `ManualTriggerJson` verbatim; a trimmed copy was refused on import ("can't find subprocess").
- Subprocess GUIDs are per-Tenant like task GUIDs: bind with `--subprocesses-from <export from the target Tenant that calls them>`. A `subprocesses:` entry with only `parameters` synthesises text parameters; prefer the export.

## Spec format (diagram only)

JSON, flat, in Frends vocabulary, no coordinates; see `assets/examples/order-sync.diagram.json`.

```json
{"name": "...", "process_id": "Process_1",
 "nodes": [{"id": "Fetch", "shape": "task", "label": "HTTP Request orders", "parent": "Scope_1"},
           {"id": "Catch_1", "shape": "catch", "label": "On error", "parent": null}],
 "flows": [{"id": "f1", "source": "Start", "target": "Fetch", "label": ""},
           {"id": "f9", "source": "Scope_1", "target": "Catch_1", "label": ""}],
 "artifacts": [{"id": "Note_1", "kind": "text_annotation", "text": "Retries 3x", "annotates": "Fetch"}]}
```

`parent` is the id of the enclosing `scope`/`foreach`/`while` (null at top level); a container needs its own `scope_trigger` start node. A flow's two ends must share a parent. A `catch` is wired as Frends wires it: a flow from the Task, Scope or Call Subprocess it guards, and one flow on to its handler (an older spec's `attached_to` is still accepted and turned into that flow). `artifacts` take `text_annotation` (`annotates`), `data_object_reference` / `data_store_reference` (`written_by`) and `group` (`members`); any node may carry a `color`.

## Workflow for producing a Process

1. **Write the spec** (YAML). `assets/examples/order-sync.yaml` shows the legacy form; `assets/examples/all-shapes-6.3.yaml` uses every 6.3 construct. Anything beyond Manual Trigger, HTTP Request, Assign Variable, Code Task, Exclusive Decision, Foreach, While, Return, Throw and Process Variables needs `target: "6.3"`. Design with this skill's rules: Process Variables for configuration (values are JSON), failure paths end in Throw after a Catch rejoins, retries on network-facing Tasks, the `#result` limits.
2. **Bind what lives in the Tenant.** The HTTP Request Task binds to the public templates' GUID; if the target Tenant holds it under another GUID, pass `--tasks-from <an export from that Tenant using the Task>`. Subprocesses bind by name with `--subprocesses-from <an export of the Subprocess, or of a Process that calls it>`; a Subprocess generated in the same session binds from its own generated file.
3. **`generate`.** It refuses what Frends would refuse (with the Frends error it prevents), validates, and prints byte count and md5.
4. **`picture --check` the result and look at it.** Layout problems are obvious by eye and invisible to a passing validator.
5. **Hand over files, in import order:** Subprocesses (including a Conditional Trigger's condition Subprocess) before the Processes that use them; an MCP-Trigger tool Process imported and activated before the AI Connector Process that calls it. Re-importing an existing GUID: choose a new version of the existing Process.
6. **Steps files cannot carry**, to tell the user: link an API Trigger Process to its API (*Link Process* in API Management, or the Frends MCP server) after importing the API from the same OpenAPI document; give queue and hub Triggers real connection settings before activating; an external MCP client needs a Private Application token with an `mcp_tools` claim (an AI Connector in the same Agent Group does not).

## When an import or run fails

- One change per import. Round trips are slow and human-mediated.
- When an import fails, bisect with minimal generated files; do not reason about the large one. "This is the only difference, so it must be the cause" is usually wrong — most differences between two exports are inert.
- Give every test import a fresh identity: `generate --fresh` (new name; the process GUID is always new unless the spec pins `unique_identifier`). Repeating an identity has returned a stale earlier error.
- A truncated file fails with `Deserializing import file failed, it does not seem to be in JSON format` — that is the delivery channel, not the content. Pasted text has broken above roughly 10,000 characters.
- An import that succeeds can still fail at run start or at the first shape: run the Process once after importing it.

## Format facts the docs do not state

Evidence levels: **[docs]** = stated on docs.frends.com. **[corpus]** = counted over the 77 public FrendsTemplates (Frends 5.7.x and 6.0.2); re-derivable by anyone with `python3 -m frendsgen selftest` and the `diagram` measuring tools.. Unmarked format facts describe how Frends imports a file. Treat **[corpus]** counts as observations about a sample, not as a specification — re-derive when the Frends version moves.

**Shape `Type` → BPMN element**

The Platform API `ElementType` enum names the Types; the table gives the element each is drawn as. Up to 23 the enum and exports agree; after that the enum (which ends `…, DataStoreReference, NativeAi`) is out of date.

| Type | Element | Shape |
|---|---|---|
| 0 | `startEvent` | Trigger (`$type` per Trigger below) |
| 1 | `task` | Task |
| 2 | `exclusiveGateway` | Exclusive Decision |
| 3 / 4 | `sequenceFlow` | plain flow (no entry) / Exclusive Decision branch |
| 5 | `endEvent` | Return |
| 6 | `intermediateThrowEvent` + `signalEventDefinition` | Throw |
| 7 | `callActivity` | Call Subprocess; `SelectedTypeId` = Subprocess GUID |
| 8 | `subProcess`, no loop element | Scope |
| 9 | none | `ParallelForeach`: enum member; the editor has no parallel Foreach |
| 10 / 11 | `subProcess` | Foreach / While |
| 12 | `scriptTask` | Assign Variable **and** Code Task |
| 13 | `startEvent` | start event inside a container |
| 14 | `intermediateCatchEvent` + `signalEventDefinition` | Catch — reached by a plain flow, **not** a `boundaryEvent` |
| 15 / 16 | `inclusiveGateway` / `sequenceFlow` | Inclusive Decision and its branches |
| 17 | `endEvent` + `signalEventDefinition` | Intermediate Return — **not** the Throw element |
| 18 | none, Id `globalErrorHandler` | Subprocess to call on unhandled error |
| 19 | none, Id `FrendsTestElementId` | the editor's scratch entry |
| 20 / 21 | `businessRuleTask` | Shared State / DMN Task (Type alone separates them) |
| 22 / 23 | `dataObjectReference` / `dataStoreReference` | artifacts (the 5.7/6.0 corpus used 21/22) |
| 24 | `intermediateCatchEvent` + `messageEventDefinition` | Checkpoint |
| 25 | `intermediateCatchEvent` + `timerEventDefinition` | Scheduled Resume |
| 26 | `intermediateCatchEvent` + `messageEventDefinition` | Signal Resume (`useSignalRehydrationMode`) |
| 27 | `task`, 199×131 | AI Connector; `SelectedTypeId` `NativeAi` |

Trigger `$type`s: `ManualTrigger`, `HttpTrigger`, `HttpApiTrigger`, `FileWatchTrigger`, `ScheduleTrigger`, `ConditionalTrigger`, `McpTrigger`, `TcpTrigger`, `AzureEventHubTrigger`, `RabbitMQTrigger`, `QueueTrigger` (AMQP; the editor labels it "Queue"), `ServiceBusTrigger`. The config is raw JSON, written identically as the shape's `Parameters` and as `TriggersJson[].config`.

Wiring facts:
- A Catch is a second outgoing flow from the guarded Task, Scope or Call Subprocess to the Type 14 event; the Catch's single successor rejoins at the guarded shape's other successor. Its `Parameters` is `{"expression": "error"}` — the error variable's name as a raw string.
- An Intermediate Return is a second outgoing flow from its activity to the Type 17 event.
- The Scheduled Resume loop: Checkpoint → Exclusive Decision → (yes) continue / (default) Scheduled Resume → back into the same Checkpoint. It is the only cycle seen.
- Branches merge straight into the next activity; no joining gateway. An Inclusive Decision gateway has empty `Parameters` and a `default=` flow; each Type 16 branch carries its own `expression` (empty on the default).
- The unhandled-error Subprocess registers in `UsedSubprocessesJson` (`__localCall`) and `LinkedSubProcess` even when nothing else calls it. `PreserveReferencesAtCheckpoint` is a per-Process setting, independent of the shapes.
- A Process with no Tasks exports `LinkedTasks: {}`. Event definitions carry no id. A new field mode, `list`, appears on the AI Connector.
- Leaves that are not `{mode, value}` cells: Trigger config, the Catch expression, Foreach `variable`, Shared State `ttlMultiplier`/`throwIfFalse`/`isGlobalScope`, several AI Connector fields, DMN `dmnXml`/`decisionId`/`parameters`.

- `ElementParameters` entries are keyed by `Id` (not `ElementId`) and always carry the same 12 keys in the same order. Every parameter leaf is `{"mode": ..., "value": ...}`. **[corpus]**
- A sequence flow has an `ElementParameters` entry **iff** its source is a decision (575/575 vs 0/697). **[corpus]**
- Foreach = `multiInstanceLoopCharacteristics isSequential="true"`; While = `standardLoopCharacteristics`. On a plain `task`, `standardLoopCharacteristics` means **retry is enabled** (40/40). **[corpus]**
- Assign Variable vs Code Task: the *presence* of `useStatementMode` marks a Code Task; its value does not. Size agrees (30×30 vs 100×80) on all but three shapes. **[corpus]**
- Every exclusive gateway has `default=`; `IsDefault` plus that attribute are authoritative, the "yes"/"no" label is cosmetic (1 of 286 is inverted). **[corpus]**
- Return, Throw, Catch and Intermediate Return names live on the BPMN `name` attribute only. Writing them to `ElementParameters.Name` as well fails the import with `Sequence contains no matching element`. **[corpus]**
- A Foreach exposes `#var.<item>` and `#var.<item>_index`. **[corpus]**
- Shape sizes (36×36 events, 50×50 gateways, 100×80 tasks) and `isMarkerVisible` are bpmn.io conventions, not Frends house style. What *is* Frends style: no pools or lanes, terminals hung below the decision that reaches them, and expanded containers sized to content. **[corpus]**
- Template vs Process import differences (`GraphJson`, `Modifier`, `UsedTasksJson` casing, where Process Variables live) and per-installation task GUIDs: see `templates-and-exports.md`.
- The validator checks Catch wiring (one handler, rejoin at the guarded shape's successor, never on a Foreach), event definitions per Type, Subprocess GUIDs against `UsedSubprocessesJson`, and that every `#result[Name]` names a shape. It does not check the `#result`-in-error-path rule (SKILL.md), which is about what an expression means, not how the file is shaped.
