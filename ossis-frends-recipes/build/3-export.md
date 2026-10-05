# Build prompt: Frends process export generator

Build a tool that turns an integration spec into a `process.json` that Frends
imports as a working Process — diagram, shape parameters, trigger, task bindings
and Process Variables.

This prompt is written to be re-run. The scope it describes is bounded by the
corpus available when it was written; with a richer corpus the same method
produces a more complete tool, and the sections below say where to widen it.

## What you can assume exists

- **A `frends` skill** covering platform semantics: reference values (`#var`,
  `#env`, `#result`), Handlebars vs C# evaluation, the shape catalogue, task
  behaviour, and the documented limitations on `#result[Name]`. Load it. Do not
  re-derive platform behaviour it already states.
- **BPMN diagram tooling** that emits valid BPMN 2.0 with correct DI geometry.
- **A corpus of real exports.** The public `FrendsTemplates` repo (77 templates)
  is what was available. Anything you cannot check against real exports is a
  guess, and guesses in this format fail late and quietly.

The diagram tooling gets you one field of roughly 29. It produces a picture. A
Process is the picture plus `ElementParameters`, and the whole difficulty lives
in keeping those two consistent.

## The corpus is a sample, not the specification

The public templates cover **14 of the 25 documented shapes**. Absent entirely:
Catch, Call Subprocess, DMN Task, AI Connector, Checkpoint, Scheduled Resume,
Signal Resume, and every artifact type. The templates also carry 662 artifact
elements (172 annotations, 163 groups, 210 associations) that any spec-driven
regeneration discards, so generated diagrams are visibly barer than hand-built
ones even where the runtime behaviour matches.

Catch is the consequential gap. Error handling appears in nearly every real
integration and there is no public example of its serialised form.

**If you have access to a wider set of real exports — an internal tenant, a
customer estate, exports you build by hand in the editor — use it.** Corpus
coverage is what decides how much this tool can support. Authoring six or eight
Processes in the editor that exercise the constructs you want, then exporting
them, is a better investment than any amount of inference from the docs. Prefer
that to guessing, always.

## The one architectural requirement

BPMN XML and `ElementParameters` must be emitted from **one walk over one node
list**, with each node's id allocated exactly once before emission and both
emitters reading that same id off the same object.

Do not call the diagram tool independently and match shapes up by name or
position afterwards. Drive it from your intermediate representation, so that
divergence between the two representations is impossible by construction rather
than merely tested for. Then test for it anyway, from outside.

The IR is also the human review point: a spec-to-process pipeline makes design
choices (which task, loop vs multi-instance, where error handling sits), and a
reviewable IR is where a person catches a wrong choice before anything is
generated.

## Scope

Pick the supported task set by **corpus coverage, not by importance** — you need
many real instances to check output against. With the public templates that
means `Frends.HTTP.Request`: 30 of 77 templates, 84 shapes.

### In scope with the public corpus

Manual Trigger; `Frends.HTTP.Request`; Assign Variable; Code Task (expression
and statement mode); Exclusive Decision with an else-branch that either
terminates or merges back to the step after the decision; Foreach; While;
Return; Throw; Process Variables.

### Out of scope, and why

| Excluded | Reason |
|---|---|
| Every other Task | No parameter schema without corpus instances. The mechanism generalises; the schemas do not. |
| Subprocesses | `LinkedSubProcess`, GUID resolution and the target-tenant precondition are all unexercised. |
| Every trigger but Manual | Schedule, HTTP/API, File and others each have their own config schema and evaluation rules. API triggers additionally bind to an API Management endpoint that must exist. |
| Environment variables (`#env`) | The templates are `#var`-only for portability, so `RequiredEnvironmentVariables` is always empty and the closure rule is never exercised. |
| **Scope + Catch** | No `boundaryEvent` and no plain Scope anywhere in the corpus. The most important gap: without it the tool cannot express the error handling most real integrations need. |
| Inclusive Decision, Shared State, DMN, AI Connector, Checkpoint, Resume shapes | Documented, absent from the corpus. |
| Artifacts — annotations, groups, associations, data objects and stores | No runtime behaviour, but their absence makes generated diagrams look sparse next to hand-built ones. |
| Promoted result values | Half-present in the shape record; `PromotedResultVariablesJson` never exercised. |
| Arbitrary flow graphs | The IR is a tree of sequences. Multiple predecessors, merges to anywhere other than the decision's successor, and multiple start events are all unsupported. |

When the spec asks for something the IR cannot express, **refuse and name the
element**. Never approximate.

## What the corpus appeared to say

As of today, across 77 public process templates, these held. They are
observations about one sample of files produced by a handful of Frends versions
(5.7.x and 6.0.x). They may already be untrue for other versions in use now, and
nothing here should be assumed stable going forward. Re-derive them from
whatever corpus you have.

- `GraphJson` was null throughout, so only two representations must agree, not
  three.
- No field carried a hash, signature or compiled artifact — the process record
  was plain data, which is what makes generation viable at all.
- Every task parameter leaf was `{"mode": ..., "value": ...}`, with modes `text`,
  `csharp`, `select`, `toggle`, `integer`. The editor wrote the full options
  object including defaults.
- `SelectedTypeId` used a lowercase task GUID; `UsedTasksJson` used uppercase.
- `UsedTasksJson` was not authoritative — some templates referenced a task absent
  from it, suggesting Frends rebuilds the field on save.
- A Foreach exposed both `#var.<item>` and `#var.<item>_index`. Undocumented.
- Templates kept Process Variables on the outer wrapper, with the inner
  `ProcessVariablesJson` null.
- Containers held an inner `startEvent` (Type 13, `SelectedTypeId: ""`) and ended
  in a Type 5 Return.
- Foreach containers carried `isSequential="true"`; While containers never did.
  Correlation only — never isolated in an import test.
- Geometry: task 100×80, Assign Variable 30×30, Code Task 100×80, gateway 50×50
  with `isMarkerVisible`, events 36×36, subProcess `isExpanded="true"` sized to
  content.
- `Modifier` had to be non-null. The Process import rejected null with
  `Value cannot be null. (Parameter 'modifier')`; the Template import accepted
  it. This one came from a real import, not from the corpus.

Recover the `Type` → BPMN tag mapping yourself, by joining `ElementParameters` to
the BPMN tag of the same id across your corpus. It takes one pass and you will
trust the result more.

## Build order

1. Corpus survey. Field inventory, Type mapping, geometry, parameter schemas.
2. IR and spec loader. Reject unknown constructs loudly at load time.
3. Emitter: BPMN + `ElementParameters` + envelope, one walk.
4. Validator.
5. Reverse parser: real export → IR. Not optional; see below.
6. CLI: generate, validate, and the corpus self-tests.

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
Identical layout is not a goal.

## Import testing: the expensive loop

None of the above proves Frends accepts the file. Get one generated export
through a real tenant early, before building anything on top of your format
assumptions.

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
  use.
- **Change one thing per import.** Round trips are slow and human-mediated; a
  batch of changes yields one bit of information about several hypotheses.
- When a failure needs a hypothesis, **bisect with minimal generated files**
  rather than reasoning about the large one.

## Two failure modes to guard against

**"This is the only difference, so it must be the cause."** These files differ in
many ways at once and most differences are inert. Two confident
single-difference diagnoses were wrong before the real cause surfaced. Prefer a
bisect that can falsify to a diff that can only confirm.

**Reasoning on top of unverifiable results.** If the channel carrying a file to
the tenant can silently alter it, every result through that channel is
uninterpretable — including the successes. Fix the channel before spending more
round trips on it.

## Deliverables

- The tool, with a CLI: `generate` (spec → export, both ProcessExport and
  Template wrapper forms), `validate`, and the corpus self-tests.
- A spec format, documented by a worked example exercising every supported
  construct.
- A README stating: what is supported and what is not, the format observations
  with the corpus and versions they came from, what each test loop proves, and
  explicitly what has never been verified against a real import.