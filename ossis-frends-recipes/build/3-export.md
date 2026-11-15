# Build 3 — the process export generator (`scripts/frendsgen/`)

Third of four build prompts. Read `README.md` in this folder first: it says what this one
may write, what it receives from the other two, and in which order they run.

---

Build a tool that turns an integration spec into a `process.json` that Frends
imports as a working Process — diagram, shape parameters, trigger, task bindings
and Process Variables.

This prompt is written to be re-run. The scope it describes is bounded by the
corpus available when it was written; with a richer corpus the same method
produces a more complete tool, and the sections below say where to widen it.
Rebuild only when the inputs change — a richer corpus, a target tenant's own
exports, a Frends MCP connector, or a Frends version whose imports behave
differently. Do not rebuild for the prompt's sake.

## 0. Inputs

- **Required when it exists: the previous version of this generator**
  (`scripts/frendsgen/`, `assets/examples/`, `references/generator/README.md`). It produced
  Processes that imported and ran on a real Tenant, and the comments that quote
  Frends errors record why its refusals exist. Start from it, not from a blank
  page. Keep its behaviour unless you have a strong reason to believe it is
  wrong: corpus or reference-export evidence that contradicts it, a failed
  import or run, or a live docs page that states otherwise. A cleaner design, a
  different reading of the docs, or "I would have done it differently" is not
  such a reason. When you do change a behaviour, say in `references/generator/README.md`
  what the old version did and what evidence overturned it. Keep every refusal
  it makes unless the same standard of evidence shows the refusal is wrong.
- **Required:** a zip of real exports. Public data means the `FrendsTemplates`
  repo. Treat it as a sample, not the specification (below).
- **Required:** this skill's `SKILL.md` and `references/`, for platform
  semantics — reference values (`#var`, `#env`, `#result`), Handlebars vs C#,
  the shape catalogue, task behaviour, the limits on `#result[Name]`. Read them.
  Do not re-derive what they state.
- **Required:** `frendsdiagram`, built by the second prompt. You drive its
  layout function from your own node list; you do not call its CLI and you do
  not write a second layout engine (see the architectural requirement). If the
  package does not honour the interface described in `2-diagram.md` step 7, fix
  it there, not by working around it here.
- **Optional, and the single highest-value input if it ever exists:** one or
  more ProcessExports from the *target* tenant. One such file answers more
  format questions in one read than rounds of import bisection. When it
  arrives, run the corpus survey on it first, before anything else. **Use it;
  never ship it.** See "Nothing tenant-specific is stored".
- **Required since 6.3: the shape reference export**
  (`assets/fixtures/shapes-6.3.json`). One ProcessExport made in
  the Frends 6.3.2 Process Editor that places one of every shape and eleven
  Triggers, scrubbed of tenant identifiers (one placeholder per original
  GUID). The fixtures README describes in words what it does not place: Catch
  on a Call Subprocess, the unhandled-error Subprocess, the Scheduled Resume
  loop and the Service Bus Trigger. Together they are the answer key
  for every construct beyond the public corpus: rebuild each shape's
  `ElementParameters` entry from them by Id, as the corpus is the answer key
  for HTTP Request. When the Frends version moves, ask for a new set built the
  same way and re-run the fixture tests before anything else.
- **If a Frends MCP connector is available**, use it for three things: fetch
  real exports into the corpus, list installed tasks and their GUIDs, and import
  generated files directly. That last one replaces the human-mediated,
  truncation-prone paste channel described under import testing, and changes
  the economics of every loop below. A connection is only a better input
  channel here: what the skill tells its *user* about the MCP server is build
  4's, so do not describe its guides or tools in `process-generation.md`. When
  an import or a task binding came through the server rather than a human,
  say so in `references/generator/README.md` next to the evidence it produced.
- **A human with a tenant** who will import files you hand them. Assume that
  channel corrupts files above roughly 10,000 characters unless the file is
  delivered as a download and checked by md5.

## The corpus is a sample, not the specification

The public templates cover **14 of the 25 documented shapes**. Absent entirely:
Catch, Call Subprocess, DMN Task, AI Connector, the Long-running suspend/resume
shapes, and every artifact type. The 6.3.2 shape reference export and its README (inputs)
fill every one of those gaps, but only as single instances: they fix the
serialised form, not the range of values a real Process puts in it. The
templates also carry hundreds of artifact elements (annotations, groups,
associations) that a spec-driven importable export discards.

Worse than missing coverage: **the public templates actively mislead on the
Process import path.** They are all Template exports. Fields that are null in
every one of them are rejected as null by the Process import (see "What was
learned"). A corpus of one export kind teaches you that kind's rules only.

**If you have access to a wider set of real exports — an internal tenant, a
customer estate, exports you build by hand in the editor — use it.** Corpus
coverage is what decides how much this tool can support. Authoring six or eight
Processes in the editor that exercise the constructs you want, then exporting
them by the *Process* export, is a better investment than any amount of
inference from the docs. Prefer that to guessing, always.

## The one architectural requirement

BPMN XML and `ElementParameters` must be emitted from **one walk over one node
list**, with each node's id allocated exactly once before emission and both
emitters reading that same id off the same object.

Do not call the diagram tool independently and match shapes up by name or
position afterwards. Flatten your intermediate representation into the diagram
layout's node-and-flow spec, keyed by the ids you already allocated, call its
layout function, and copy back only geometry. Divergence between the two
representations is then impossible by construction rather than merely tested
for. Then test for it anyway, from outside.

There is one layout engine in the package. The spec-level model here is a tree
of sequences and the layout handles arbitrary graphs; flattening tree to graph is
the easy direction, which is why the dependency points this way.

The IR is also the human review point: a spec-to-process pipeline makes design
choices (which task, loop vs multi-instance, where error handling sits), and a
reviewable IR is where a person catches a wrong choice before anything is
generated.

## Nothing tenant-specific is stored

This tool is published. A task GUID can differ between Tenants (below), so the
target may hold a task under a different GUID than the templates use — and the
tool must not carry any Tenant's GUIDs.

- Ship only the bindings found in the public corpus, and bind to them by
  default. They are public, and they are what the generator uses when the user
  supplies nothing else.
- When the target's GUIDs differ, read them **at run time** from an export the user supplies
  (`generate --tasks-from <export>`), matching tasks by `LinkedTasks[].PackageId`,
  the only place an export names a task in words. `lift` and the self-tests learn
  bindings the same way from whatever files they are pointed at.
- No tenant export, tenant GUID, tenant URL, user name or email in code, tests,
  examples, docs or bisect files that get committed. Tests that need a second
  installation use a synthetic GUID. Examples lifted from public templates get
  their `modifier` replaced.
- Bisect ladders are session artifacts. Hand them to the human; do not ship them.

## Scope

Pick the supported task set by **corpus coverage, not by importance** — you need
many real instances to check output against. With the public templates that
means `Frends.HTTP.Request`, the only task with dozens of instances.

### In scope with the public corpus

Manual Trigger; `Frends.HTTP.Request`; Assign Variable; Code Task in statement
mode; Exclusive Decision with an else-branch that either terminates or merges
back to the step after the decision; Foreach; While; Return; Throw; Process
Variables.

### In scope with the 6.3.2 shape reference export (`target: "6.3"`)

Every documented shape and all twelve Triggers: Scope; Catch (as an attribute
of the Task, Scope or Call Subprocess it guards, with one handler shape that
rejoins at the guarded shape's successor); Intermediate Return; Call
Subprocess and the unhandled-error Subprocess (bound by name from the target
Tenant's `LinkedSubProcess`, the way task GUIDs are bound); Inclusive
Decision; Shared State `AddOrUpdate`; DMN Task (built from a table, or carried
verbatim); AI Connector (parameters passed through from a lifted export);
Checkpoint; Signal Resume; the Checkpoint -> decision -> Scheduled Resume loop
as one bounded construct; multiple Triggers; Manual Trigger parameters.

These are rebuilt field for field from the reference export and its README.

### Out of scope, and why

| Excluded | Reason |
|---|---|
| Every Task but HTTP Request | No parameter schema without many real instances. The mechanism generalises; the schemas do not. HTTP Request is the one in the public templates. |
| Shared State operations other than `AddOrUpdate` | Only `AddOrUpdate` appears in the reference export. |
| Environment variables (`#env`) closure | The templates are `#var`-only, so `RequiredEnvironmentVariables` is never exercised. Bare `#env` references in Trigger credential fields are allowed; the closure list is not computed. |
| Code Task in expression mode (`useStatementMode: false`) | No instance in the corpus or the reference export. Emit it if asked. |
| Artifacts in an importable file | No runtime behaviour. The diagram side draws them. |
| Promoted result values | `PromotedResultVariablesJson` is never exercised. |
| Arbitrary flow graphs | The IR is a tree of sequences plus two fixed attachments (Catch, Intermediate Return) and one fixed cycle (the Checkpoint / Scheduled Resume loop). Merges anywhere other than the step after a decision are unsupported. |
| A Catch on a Foreach or While, or a Catch handler of more than one shape | A Foreach or While cannot have a Catch. The docs allow exactly one shape after a Catch, so a decision or `wait_until` cannot be the handler (use a Scope). |
| Catch and Intermediate Return on the same shape | The Task reference allows one flow out "with optionally an Intermediate Return or Catch" in addition. |

When the spec asks for something the IR cannot express, **refuse and name the
element**. Never approximate. The diagram side may draw what this side refuses;
that asymmetry is deliberate — a wrong picture is cheap, a wrong
`ElementParameters` entry is a failed import.

## What was learned, and how well each thing is known

As of today, from 77 public templates (Frends 5.7.x and 6.0.x) plus a small
number of imports into one 6.x tenant. These are observations about one sample
and one installation. They may already be untrue for other versions in use now.
Re-derive from whatever corpus you have; where a claim came from an import
rather than the corpus it is marked, because that is the stronger evidence.

**From the corpus:**

- No field carried a hash, signature or compiled artifact — the process record
  was plain data, which is what makes generation viable at all.
- Every task parameter leaf was `{"mode": ..., "value": ...}`, with modes `text`,
  `csharp`, `select`, `toggle`, `integer`. The editor wrote the full options
  object including defaults.
- `SelectedTypeId` used a lowercase task GUID; `UsedTasksJson` used uppercase.
- `UsedTasksJson` was not authoritative — some templates referenced a task absent
  from it, suggesting Frends rebuilds the field on save.
- A Foreach exposed both `#var.<item>` and `#var.<item>_index`. Undocumented.
- Containers held an inner `startEvent` (Type 13, `SelectedTypeId: ""`) and ended
  in a Type 5 Return.
- Foreach containers carried `isSequential="true"`; While containers never did.
  Correlation only.
- Only sequence flows leaving a gateway carry an `ElementParameters` entry;
  plain flows have none. Corroborated by the tenant export.
- Return and Throw carry their name on the BPMN element only; the
  `ElementParameters` entry has `Name: null`. Corroborated by the tenant export,
  and emitting a name there produced a parse error on import.

**From imports (Process path unless stated):**

- `Modifier` must be non-null. Rejected with
  `Value cannot be null. (Parameter 'modifier')`; the Template path accepts null.
- `GraphJson` is null in every template and that value is **rejected** on the
  Process path (`not-null property references a null … Process.GraphJson`).
  `""` imports, and is exactly what the tenant's own ProcessExport carries.
  `"{}"` produced `Old frends 4.2 type Processes are not longer supported`, but
  that file also differed in task binding, so treat the `"{}"` reading as
  plausible, not confirmed. Emit `""` on the Process path, null on the Template
  path.
- Process Variables sit on the outer wrapper in Templates and on the process
  record's `ProcessVariablesJson` in ProcessExports. Both forms confirmed.
- `UsedTasksJson` GUID casing follows the export form: uppercase in Templates,
  lowercase in the tenant's own ProcessExport.
- **Task GUIDs can differ between Tenants.** The same task package has been
  seen under a different GUID in a Tenant than in the public templates: same
  schema, different id. The generator binds to the GUID found in the public
  templates by default, prints every GUID it bound, and warns that the target
  Tenant may hold the task under a different one; `--tasks-from <export>`
  rebinds to the target's GUIDs.

**A misreading to avoid.** The docs say a shape's `#result` must not be used in
the error-handling path that follows it. That is about **Catch** paths — the
Catch handler and the decision a Catch path merges into. A decision that checks
a completed HTTP Request's status code, and a Throw on its else-branch that
interpolates that result, is not an error path; every public template does it
and none of them contains a Catch. Do not implement this as a validator rule, and
do not report the templates as violating it. An earlier run did both.

Recover the `Type` → BPMN tag mapping yourself, by joining `ElementParameters` to
the BPMN element of the same id across your corpus; cross-check the type *names*
against the published `ElementType` enum (see `2-diagram.md` step 3), and then
**assert in a test that it agrees with the diagram package's table**. Two tables derived separately
are useful exactly once; after that they are a way to drift.

## Build order

1. Corpus survey. Field inventory (classify each field as constant / derived /
   free, separately per export kind), Type mapping, parameter schemas. Geometry
   is the diagram package's business, not yours.
2. IR and spec loader. Reject unknown constructs loudly at load time, and reject
   values the platform caps (retry count is 1–10).
3. Plan: one node list, ids allocated once, layout delegated (above).
4. Emitter: BPMN + `ElementParameters` + envelope, one walk. Both export forms.
   Compact JSON separators for the embedded strings — file size matters for the
   delivery channel.
5. Validator. A `#result[Name]` that names no shape is an **error**, not a
   warning: Frends will not compile it. Confirm on the corpus that the rule
   never fires on real files before relying on that.
6. Reverse parser: real export → IR, and IR → spec. Not optional; see below.
7. CLI, runnable as `python3 -m frendsgen`: `generate` (`--form`, `--tasks-from`,
   `--fresh` to give a test import a unique name; the GUID is always new unless
   the spec pins it), `validate`, `lift [--spec]`, `selftest`, and `picture` —
   any export or `.bpmn` to SVG through the diagram package's renderer, with
   `--check` running its geometry validator. `picture` is how a generated file
   gets looked at, and looking is a required step.

`generate`, `validate` and `lift` must work with the standard library plus
PyYAML; only `picture` may need `lxml`. The package must run from a read-only
directory.

## Three test loops, in order of what they prove

**Calibrate the validator against untouched corpus files.** Anything it reports
there is a bug in the validator, since those files came out of Frends. Expect a
lot at first and treat each as a finding: is the rule wrong, or merely stricter
than Frends' own output? Do not move on until it is clean across the corpus.

**Rebuild real task parameters and diff.** Read every corpus instance of your
supported task back into the IR, re-emit, and compare against what Frends wrote.
Target byte-identical on every instance. The answer key is Frends output, so this
is not circular the way a round-trip through your own generator would be. It is
the strongest evidence available without a tenant.

**Lift whole real Processes into the IR and regenerate.** This tells you the IR
covers what real Processes actually use, and it finds emitter bugs the forward
path cannot. Writing the reverse parser surfaced a missing `default` flow on
decisions nested inside an else-branch, a spec loader that rejected a shape the
corpus contains, and a validator counting sequence-flow labels as shape names.

Compare rebuilt against original on shape-Type histogram and on task parameter
payloads. Identical histogram plus byte-identical parameters is a strong result.
Identical layout is not a goal. Report the number of corpus processes that fit
the IR as the coverage number, without rounding it up.

Then one check the loops above do not make: every generated example must pass
the **diagram** validator too, and you must render at least the largest one and
look at it.

## Import testing: the expensive loop

None of the above proves Frends accepts the file. Get one generated export
through a real tenant early, before building anything on top of your format
assumptions — and start with the smallest file that can fail: a Manual Trigger
and a Return, no task. The first success settles the envelope; everything
after that isolates one construct at a time.

- **Randomise the process GUID and name on every test import.** There is
  evidence the platform serves a cached result for a repeated identity, which
  produces stale errors that look like real findings.
- **Verify file integrity before reading anything into a failure.** Record byte
  count and md5 at generation; confirm both at the tenant. A truncated file
  produces `Deserializing import file failed, it does not seem to be in JSON
  format (Parameter 'exportContainerJson')`, which looks like a content bug and
  is not.
- **The Template import and the Process import validate differently.** A file the
  Template path accepts can fail on the Process path. Test the path you intend to
  use, and say which path each finding came from.
- **Change one thing per import.** Round trips are slow and human-mediated; a
  batch of changes yields one bit of information about several hypotheses.
- **Hand over a numbered ladder, not a single file.** For each file: what it
  changes relative to the last one that imported, the predicted result, and what
  each possible outcome would mean. The human imports in order and stops at the
  first surprise. This turns one round trip into several bits.
- Include a file expected to *reproduce* a known failure. A hypothesis you cannot
  reproduce on demand is not confirmed.
- **The moment the human can export one Process from the target tenant, ask for
  it instead of another bisect round.**

If the layout engine or the emitter changed since the last accepted import, say
so in the README: acceptance belongs to a file, not to the tool.

## Two failure modes to guard against

**"This is the only difference, so it must be the cause."** These files differ in
many ways at once and most differences are inert. Two confident
single-difference diagnoses were wrong before the real cause surfaced, and a
third (the `"{}"` reading above) is still only plausible. Prefer a bisect that
can falsify to a diff that can only confirm.

**Reasoning on top of unverifiable results.** If the channel carrying a file to
the tenant can silently alter it, every result through that channel is
uninterpretable — including the successes. Fix the channel before spending more
round trips on it.

## Deliverables

Into the skill, and nowhere else:

- `scripts/frendsgen/` — the package, with the CLI above, both export forms and
  the corpus self-tests. `scripts/tests/` — unit tests that pin every
  import-path rule, the binding-by-PackageId behaviour, and the agreement of the
  two shape tables.
- `assets/examples/` — a worked spec exercising every supported construct, and
  the largest public process that fits the IR, produced by `lift --spec`.
- `references/generator/README.md` — usage; architecture; scope; what each test proves with
  its current numbers.
- **`references/process-generation.md`** — this build owns it. It is what an
  agent using the skill reads, so it carries: which entry point to use when; the
  scope of each side; **both spec formats, documented** (an agent must be able
  to write a spec without reading `spec.py`); the workflow including
  `--tasks-from` and the look-at-it step; import discipline; and the
  format facts, with **[corpus]** on counts over the public templates.
- The section "The two import paths validate differently" and the
  task-GUID paragraph in **`references/templates-and-exports.md`**.
  The rest of that file belongs to the skill build; add, do not rewrite.
- The one router row and the one sentence in `SKILL.md` that point at the tool.
  Nothing else in `SKILL.md`.

Finish by acting as the skill's user: with only `SKILL.md` and `references/`
open, write a new spec for a small integration, including one typo in a
`#result` name and one unsupported construct. Both must be caught with a message
that names the problem. If you had to open the source to write the spec, the
reference is not done.

Then run the generator scenarios (G) in `scenarios.md` the same way, and
report pass/fail for each.
