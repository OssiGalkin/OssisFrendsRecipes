# Generating Processes and diagrams

`scripts/frendsgen` is one Python package with two entry points that share one layout engine:

| You want | Use | Output | Can Frends import it? |
|---|---|---|---|
| A working Process from a spec | `python3 -m frendsgen generate spec.yaml -o process.json` | ProcessExport (or `--form template`) | Yes, within the scope below |
| A picture of a design — for a spec, review, blog post | `python3 -m frendsgen.diagram.generate spec.json out.bpmn` | `.bpmn` with full layout | **No.** A diagram has no `ElementParameters`, so no functionality |
| A picture of an existing export | `python3 -m frendsgen picture export.json -o out/` | SVG drawn from the file's own layout | n/a |
| An editable spec from an existing export | `python3 -m frendsgen lift export.json --spec -o my.yaml` | YAML | n/a |

Run everything from `scripts/` (a read-only skill directory is fine; write outputs elsewhere with `-o`). `generate`, `validate` and `lift` need only Python 3, plus PyYAML for YAML specs (JSON specs work without it). `picture` and the `diagram` validate/render/extract tools also need `lxml`. Full usage, tests and architecture: `scripts/README.md`.

**"Make me a Frends process" usually means a picture.** Ask which one is wanted when it is not obvious. The two scopes differ on purpose: a wrong picture costs nothing, a wrong `ElementParameters` entry is a failed import.

## Scope

**Importable export (`generate`)** — Manual Trigger; `Frends.HTTP.Request`; Assign Variable; Code Task; Exclusive Decision whose else-branch either terminates or merges back to the step after the decision; Foreach; While; Return; Throw; Process Variables. Anything else is **refused by name** at load time, never approximated. Not supported: every other Task and Trigger, Call Subprocess, `#env` references, **Scope + Catch**, Inclusive Decision, Shared State, DMN, AI Connector, Long-Running Process shapes, artifacts, promoted values, arbitrary flow graphs (the model is a tree of sequences).

The boundary is set by evidence, not importance: a construct is supported only if the public template corpus has enough real instances to check output against byte for byte. Catch is the gap that matters — there is no public example of its serialised form.

**Diagram only (`diagram.generate`)** — the full shape vocabulary, including what the export side refuses: `trigger`, `scope_trigger`, `task`, `assign_variable`, `code_task`, `shared_state_task`, `call_subprocess`, `dmn_task`, `ai_connector`, `decision`, `inclusive_decision`, `return`, `throw`, `intermediate_return`, `scope`, `foreach`, `while`, `catch`. Arbitrary flow graphs. Catch is drawn from the docs (a `boundaryEvent`), not confirmed against any real file.

## Spec format (importable Process)

YAML or JSON. `scripts/examples/order-sync.yaml` uses every construct; `lift --spec` writes this format from any real export that fits, which is the fastest way to see a construct you care about. Unknown keys are errors, never silently dropped.

```yaml
name: Order sync                       # required
description: ...
modifier: you@example.com              # any non-null string
trigger: manual                        # the only trigger
variables:                             # Process Variables; value is a C# literal
  - {name: ShopBaseUrl, value: '"https://shop.example.com/api"', description: ...}
  - {name: ShopToken,   value: '""', secret: true}
steps:
  - assign: {variable: orders, expression: {csharp: "new JArray()"}}
  - task:
      type: http_request               # the only task
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
- A decision branch either ends in `return`/`throw` or is empty and merges back to the step after the decision. Nothing else is expressible.
- A sequence that does not end in `return`/`throw` gets a `return: #result` appended. Container bodies get their inner start event automatically.
- `http_request` params: `method`, `url`, `message`, `result_method`, `headers: [{name, value}]`, `authentication`, `username`, `password`, `token`, `timeout_seconds`, `follow_redirects`, `throw_on_error`, `allow_invalid_certificate`, `allow_invalid_charset`, `automatic_cookie_handling`, and the `certificate_*` fields (`tasks.py`).
- Pin `unique_identifier` only when you mean to overwrite that Process; otherwise every run gets a new GUID.

## Spec format (diagram only)

JSON, flat, in Frends vocabulary, no coordinates; see `scripts/examples/order-sync.diagram.json`.

```json
{"name": "...", "process_id": "Process_1",
 "nodes": [{"id": "Fetch", "shape": "task", "label": "HTTP Request orders", "parent": "Scope_1"},
           {"id": "Catch_1", "shape": "catch", "label": "On error", "attached_to": "Scope_1", "parent": null}],
 "flows": [{"id": "f1", "source": "Start", "target": "Fetch", "label": ""}]}
```

`parent` is the id of the enclosing `scope`/`foreach`/`while` (null at top level); a container needs its own `scope_trigger` start node. A flow's two ends must share a parent. A `catch` names the shape it guards in `attached_to`.

## Workflow for producing a Process

1. Write the spec (YAML; see `scripts/examples/order-sync.yaml`, which uses every supported construct). Design it with this skill's rules: `#var` Process Variables for configuration, failure paths end in Throw, retries on network-facing Tasks, the `#result` limitations.
2. **Get the target's task GUIDs.** Ask the user to export any Process from the target Tenant that uses the needed task, and pass it as `--tasks-from that-export.json`. Without it the file binds to the public templates' GUIDs and will not find its tasks in a real Tenant.
3. `generate`. It validates before writing and prints byte count and md5.
4. `picture --check` the result and **look at it**. Layout bugs are obvious by eye and invisible to a passing validator.
5. Hand over the file as a download, not pasted text, and have the md5 confirmed before reading anything into an import error.

## Import testing discipline

- One change per import. Round trips are slow and human-mediated.
- When an import fails, bisect with minimal generated files; do not reason about the large one. "This is the only difference, so it must be the cause" is usually wrong — most differences between two exports are inert.
- Give every test import a fresh identity: `generate --fresh` (new name; the process GUID is always new unless the spec pins `unique_identifier`). Repeating an identity has returned a stale earlier error.
- A truncated file fails with `Deserializing import file failed, it does not seem to be in JSON format` — that is the delivery channel, not the content. Pasted text has broken above roughly 10,000 characters.
- Import acceptance is not execution — check both. A generated Process has been imported into a Frends 6.x Tenant and run there; that is evidence for the constructs that Process contains, not for the ones it does not.

## Format facts the docs do not state

Evidence levels: **[docs]** = stated on docs.frends.com. **[corpus]** = counted over the 77 public FrendsTemplates (Frends 5.7.x and 6.0.2); re-derivable by anyone with `python3 -m frendsgen selftest` and the `diagram` measuring tools. **[import]** = observed importing generated files into one Frends 6.x Tenant; reproducible only with a Tenant. Treat both as observations about a sample, not as a specification — re-derive when the Frends version moves.

**Shape `Type` → BPMN element [docs + corpus]**

The Platform API reference publishes the `ElementType` enum (`/reference/frends-platform-api/platform-api-reference/processes.md`, in the `ElementParameters` schema), in declaration order:

> Start, Task, Decision, SequenceFlow, ConditionBranch, Return, Throw, CallActivity, SubProcess, ParallelForeach, SequentialForeach, While, Expression, SubProcessStartNode, Catch, InclusiveGateway, InclusiveDecisionBranch, IntermediateReturn, GlobalErrorHandler, TestTask, SharedState, Dmn, DataObjectReference, DataStoreReference, NativeAi

Read as 0-based indices, that enum matches the corpus exactly for every Type up to 20, and names the shapes the corpus does not contain. It also explains three findings that look like corpus trivia: a plain flow is `SequenceFlow` (3) and gets no `ElementParameters` entry, while a gateway branch is a different type, `ConditionBranch` (4), and does; Foreach is `SequentialForeach` (10), which is why its loop element carries `isSequential="true"`; and Type 12 is `Expression`, one type for both Assign Variable and Code Task. **Above 20 the numbering has moved.** In the 5.7/6.0 corpus 21/22/23 are the artifact shapes, but the current enum reads 21 `Dmn`, 22 `DataObjectReference`, 23 `DataStoreReference`, 24 `NativeAi`. So for a current export, do not assume 21 is an artifact — check the BPMN element it is attached to.

| Type | Element | Shape |
|---|---|---|
| 0 | `startEvent` | Trigger |
| 1 | `task` | Task |
| 2 | `exclusiveGateway` | Exclusive Decision |
| 4 | `sequenceFlow` | flow leaving a decision |
| 5 | `endEvent` | Return |
| 6 | `intermediateThrowEvent` + `signalEventDefinition` | Throw (Intermediate Return is indistinguishable) |
| 10 / 11 | `subProcess` | Foreach / While |
| 12 | `scriptTask` | Assign Variable **and** Code Task |
| 13 | `startEvent` | start event inside a container |
| 15 / 16 | `inclusiveGateway` / `sequenceFlow` | Inclusive Decision and its branches |
| 19 | none | `TestTask` (`FrendsTestElementId`): editor scratch entry with no diagram element |
| 20 | `businessRuleTask` | Shared State Task (not DMN) |
| 21–23 | data object / store references | artifacts **in the 5.7/6.0 corpus only** — see the numbering note above |

- `ElementParameters` entries are keyed by `Id` (not `ElementId`) and always carry the same 12 keys in the same order. Every parameter leaf is `{"mode": ..., "value": ...}`. **[corpus]**
- A sequence flow has an `ElementParameters` entry **iff** its source is a decision (575/575 vs 0/697). **[corpus]**
- Foreach = `multiInstanceLoopCharacteristics isSequential="true"`; While = `standardLoopCharacteristics`. On a plain `task`, `standardLoopCharacteristics` means **retry is enabled** (40/40). **[corpus]**
- Assign Variable vs Code Task: the *presence* of `useStatementMode` marks a Code Task; its value does not. Size agrees (30×30 vs 100×80) on all but three shapes. **[corpus]**
- Every exclusive gateway has `default=`; `IsDefault` plus that attribute are authoritative, the "yes"/"no" label is cosmetic (1 of 286 is inverted). **[corpus]**
- Return and Throw names live on the BPMN `name` attribute only. Writing them to `ElementParameters.Name` as well fails the import with `Sequence contains no matching element`. **[corpus + import]**
- A Foreach exposes `#var.<item>` and `#var.<item>_index`. **[corpus]**
- Shape sizes (36×36 events, 50×50 gateways, 100×80 tasks) and `isMarkerVisible` are bpmn.io conventions, not Frends house style. What *is* Frends style: no pools or lanes, terminals hung below the decision that reaches them, and expanded containers sized to content. **[corpus]**
- The public templates cover 14 of the documented shapes. Absent entirely: Catch, plain Scope, Call Subprocess, DMN, AI Connector, Checkpoint and the Resume shapes. **[corpus]**
- Template vs Process import differences (`GraphJson`, `Modifier`, `UsedTasksJson` casing, where Process Variables live) and per-installation task GUIDs: see `templates-and-exports.md`. **[import]**
- The validator does not check the `#result`-in-error-path rule (SKILL.md): that rule is about Catch paths, and Catch is outside the generator's scope. It does check that every `#result[Name]` names a shape that exists, and refuses to write the file if one does not.
