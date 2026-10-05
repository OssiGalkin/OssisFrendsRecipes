# Build 2 — the diagram toolchain (`scripts/frendsgen/diagram/`)

Second of three build prompts. Read `README.md` in this folder first: it says what this
one may write, what it must hand to the next one, and in which order they run.

---

I want you to build a Frends BPMN diagram toolchain. I want you to be able to
turn an integration spec into a `.bpmn` file that opens correctly in bpmn.io and
looks like a Frends Process, to validate such files, to render them as SVG/PNG
for documentation, and to reverse-engineer Frends' drawing conventions from a
corpus of real Processes.

Scope note before you start: this produces **diagrams**, not importable
Processes. A Frends Process needs a `process.json` with `ElementParameters`,
`GraphJson` and `TriggersJson`, and the actual functionality lives in
`ElementParameters`, not in the BPMN XML. Say so plainly whenever the user's
phrasing is ambiguous — "make me a Frends process" usually means a picture, but
check.

## 0. Inputs

Everything below works from public data. Take what is offered, ask for nothing
that isn't listed as optional.

- **Required:** a zip of Frends exports — Templates, Process exports, Subprocess
  exports, or a mix. Derive every constant from it. This prompt deliberately
  contains no measurements, only the traps that measuring cannot reveal.
- **Optional:** `bpmn-viewer.development.js` from the bpmn-js distribution. If
  present, you can drive it through the local Chromium and get true bpmn.io
  rendering offline (see step 1). It is licensed for this; keep its watermark
  code untouched.
- **Optional, later:** exports from a real tenant, which will contain shape
  Types the public corpus lacks. Treat them exactly like the zip — and never
  commit them, or anything derived from them that identifies the tenant.
- **If a Frends MCP connector is available**, prefer it over the zip for
  fetching real exports, and note in the README which inputs came through it.

Rebuilding this tool is only worth doing when the inputs change — a richer
corpus, a working real renderer, or a new Frends version whose exports differ.
Do not rebuild for the prompt's sake.

---

## 1. Survey the environment before designing anything

Check whether `bash` has network (usually not — `npm install` returns 403),
whether `sharp` is installed globally, whether a headless Chromium sits under
`~/.cache/puppeteer` or `/opt/pw-browsers` with `playwright` importable, and
what else is around.

This decides the architecture. If `bpmn-js` cannot be fetched you cannot render
true bpmn.io output locally, and you need your own SVG renderer to eyeball
results. `sharp`, or a playwright screenshot of the SVG, turns it into a PNG so
you can actually *look* at your output — do that constantly; most layout bugs
are obvious by eye and invisible to a passing test. Mermaid CLI works offline
but needs `PUPPETEER_EXECUTABLE_PATH` pointed at the Chrome it can't find by
itself.

If `bpmn-viewer.development.js` was uploaded: write a one-page HTML that loads
it from the local path, open it with playwright against the local Chromium, call
`importXML`, and screenshot. Report import warnings — they are the closest thing
to a ground-truth geometry check that exists here. If it fails to load, say so
once and fall back to your own renderer; do not spend the session on it.

## 2. Extract ground truth from the corpus

Build an extractor that pulls every Process out of the zip and writes, per
process, the raw `Bpmn` field as a `.bpmn` file plus a layout-free structural
spec as JSON.

Things that will bite you:

- **Wrapper keys differ by export kind.** Templates nest under
  `ProcessTemplates[] → ProcessInfo → Process`; Process exports use
  `Processes[]`. Don't key on either — walk the JSON depth-first for any object
  carrying a non-empty `Bpmn` field. That handles Subprocess exports and future
  shapes for free.
- **Files carry a UTF-8 BOM.** Open with `utf-8-sig` or parsing raises.
- `ElementParameters` may arrive as a JSON string rather than a list, and the
  key that names the element is `Id`, not `ElementId`. Check the first file
  before assuming either.

The spec carries, per node: id, Frends shape name, label, parent container,
source BPMN element. Per flow: id, source, target, label. Nothing about
coordinates — layout is the generator's job, and keeping the spec layout-free is
what makes the round-trip in step 8 meaningful.

Note what the spec necessarily drops: text annotations, groups, associations,
data references. Regenerated diagrams will be visibly barer than the originals.
If annotations matter for the deliverable, carry them through explicitly.

## 3. Map the Frends shape vocabulary from the corpus

Correlate `ElementParameters[].Type` with the BPMN element carrying the same
id. That correlation is the only way to learn which Frends shape is which BPMN
element is drawn as. Use `SelectedTypeId` and the shape labels to name each Type.

**Check your names against the published enum.** The Platform API reference
(`/reference/frends-platform-api/platform-api-reference/processes.md`, the
`ElementParameters` schema) lists `ElementType` in declaration order, which read
as 0-based indices names every Type. Use it to name what you found and to see
what your corpus is missing — but derive the *element* from the join, and expect
the numbering above 20 to differ between Frends versions. Where the enum and your
corpus disagree, the corpus wins for that corpus, and say so.

**Any Type your mapping doesn't know must be reported loudly, with example
labels — never skipped.** A silent skip produces a spec that round-trips
perfectly while missing shapes: the most dangerous failure in the pipeline,
because every downstream check reports success.

Expect unknowns. Catch, plain Scope, Call Subprocess, DMN Task, AI Connector,
Checkpoint, Scheduled Resume and Signal Resume appear nowhere in the public
template repo, so if your corpus is richer than that you will meet Types no prior
mapping covers. Identify each, then extend.

See the Appendix before you trust any Type you think you've identified.

## 4. Measure the geometry — never assume it

Write a measurement script and run it over the untouched corpus before you write
a line of generator. Measure:

- shape width × height per element type, with sample counts
- `isMarkerVisible` presence on every gateway shape, split by gateway kind
- vertical centre lines per file, and which element kinds share each one
- horizontal gaps between consecutive shapes on a row
- per sequence flow: waypoint count, which edge of the source it leaves, which
  edge of the target it enters, the vertical offset between the two centres —
  **split by the target's shape kind**, not pooled (see step 7)
- incoming/outgoing sequence-flow counts per element type

Report **shares, not modes**. "74% of gateway branches exit top or bottom" is a
very different instruction from "gateway branches exit top or bottom", and the
difference is exactly what decides whether a rule is an error or a warning in
step 6. A convention followed by every sample is a hard rule; one followed by
three quarters is house style.

Cross-check against two non-Frends references so you can tell Frends house style
from BPMN convention: the bpmn.io starter diagram (`bpmn-io/bpmn-js-examples`,
`starter/diagram.bpmn`) and a Camunda Modeler file
(`camunda/camunda-bpm-examples`, `servicetask/rest-service/invokeRestService.bpmn`).

## 5. Get semantics and connection rules from the live docs

Measurement gives geometry. The docs give meaning and the rules geometry can't
show. If the skill's `SKILL.md` and `references/` already exist (they should —
the skill is built first), read them before fetching anything: do not re-derive
what they state, and do not contradict them silently. If the docs now disagree
with the skill, report it; that is a finding for the skill build.

- `https://docs.frends.com/llms.txt` — full page index.
- **Append `.md` to any docs URL** for clean Markdown. Do this every time.
- `https://docs.frends.com/reference/shapes/shape` — the taxonomy: event,
  decision, activity, scope, long-running, artifact, sequence flow.
- Then the per-shape pages under `/reference/shapes/`, especially `task`,
  `scope-shapes/scope`, `event-shapes/catch`, `event-shapes/return`,
  `decision-shapes/exclusive-decision`.

Mine for: how many sequence flows each shape takes in and out, what may attach to
what, what must sit inside what. Record them as quoted constraints — a Task is
one flow in one out, optionally with an Intermediate Return or Catch attached; a
Scope contains exactly one Trigger; a Catch's handler must be a single shape and
the error path must rejoin the main flow immediately after the guarded shape with
no shapes in between.

Fetching constraints encountered: GitHub blocks `/tree/` and `/raw/` paths for
automated fetch but allows `/blob/`, and CDN mirrors of repo paths work.
`templates.frends.com` is client-rendered with no server-side listing, so ask for
a zip rather than trying to scrape it. The docs advertise a `?ask=` query
parameter on `.md` URLs. **Runs disagree on whether it works**: one got the page
back unchanged, and the skill build recommends it. Try it once, record what
happened in the README, and don't build a step around it either way.

## 6. Build the validator first, and calibrate it on real files

Write the validator before the generator. It's what tells you whether the
generator works, and building it second means grading your own homework.

Two severities:

- **Errors** — broken or will render wrong: dangling `sourceRef`/`targetRef`,
  `incoming`/`outgoing` lists disagreeing with the actual flows, a flow node with
  no `BPMNShape` or a flow with no `BPMNEdge`, an *exclusive* gateway shape
  missing `isMarkerVisible`, a first or last waypoint off its shape's boundary,
  overlapping shapes, an edge segment crossing an unrelated shape, and XML child
  ordering (Appendix).
- **Warnings** — house style: non-standard shape size, a gateway branch leaving
  on an unexpected edge, a straight same-row hop with extra waypoints, a main
  path that bends — scoped to flows entering the target's left edge, or it fires
  on half the shipped corpus.

**Run it over the untouched corpus before anything you generated.** Any rule that
fires on shipped Frends Processes is either wrong or belongs at warning severity.
This calibration is the whole reason the two severities exist, and it
occasionally finds real defects in the source material — worth telling the user
about.

Keep questioning rules after calibration too. A warning on your own output can
mean the rule is wrong rather than the diagram: a "too many waypoints" rule will
flag a router that correctly detoured around an obstacle. Check whether the
direct route was actually available before suppressing anything.

Two traps in the validator itself: a validator that doesn't know `subProcess`
reports the entire corpus as broken, and expanded containers legitimately enclose
other shapes, so exclude them from overlap and edge-crossing checks or every
nested process fails.

## 7. Build the generator

Input is the spec from step 2; output is `.bpmn` with full DI, plus SVG. The
caller never supplies coordinates.

**Layout.** Rank nodes by longest path from a source. Assign rows so a node
inherits its single predecessor's row — only extra gateway branches open new
rows, which is what keeps the main path straight. Compute column x cumulatively
from the widest shape in each rank plus a fixed gap, not from a fixed pitch, so
gaps stay constant across mixed widths. Centre every shape on its row's centre
line; never top-align.

**Containers.** Scope, Foreach and While nest, and on a real corpus most
processes are nested. Lay out each level recursively: deepest containers first,
their children's bounding box plus padding becomes the container's size, then the
parent level lays out with that size, then translate child coordinates down the
tree. Without this, nested processes come out as flat sibling soup.

**Routing.** Same-row forward hop is two waypoints, source right edge to target
left edge. A gateway branch to another row leaves vertically from the gateway's
top or bottom at its own centre-x, drops to the target's centre-y, then runs into
the target's left edge. A backward flow drops below every shape at its own level
and comes back up.

Then clearance-check every route against all non-container shapes, with a
fallback that searches for a free corridor. Assume any route can be blocked — see
the Appendix; four separate bugs were all this same mistake.

Use step 4's entry-side data for **placement**, not only routing. If a kind of
terminal shape is overwhelmingly entered on one edge, Frends is hanging it off
the row rather than sitting it in the row, and reproducing that placement makes
diagrams dramatically shorter than giving every branch its own full-height band.
Give a gateway's dangling terminals a shallow slot under the branching shape,
side by side rather than stacked. Decide this **per terminal kind** from your own
numbers: a Throw and a Return that follow a decision are not drawn the same way
equally often, and a rule justified by one must not be applied to the other on
its say-so.

**XML emission.** Nest children inside their parent `subProcess`. Emit `incoming`
before `outgoing`. Put `loopCharacteristics` before the flow elements (Appendix).
Set `isMarkerVisible="true"` on every exclusive gateway shape. Raise rather than
skip if a flow's two ends sit at different nesting levels — Frends never produces
those, and a silent drop would be invisible.

Expose the model in Frends vocabulary, not BPMN element names: `trigger`, `task`,
`assign_variable`, `code_task`, `decision`, `inclusive_decision`, `return`,
`throw`, `foreach`, `while`, `scope`, with nesting as a parent reference.

Build a second, separate renderer that draws an existing `.bpmn` from the layout
already in its BPMNDI, with no re-layout. That turns any Frends export into a
clean diagram for a blog post or review, and confirms your reading of the DI
matches reality.

**The interface the export generator depends on.** This is a contract, not a
style preference; the third build prompt is written against it.

- The code is a Python package, `frendsgen.diagram`, and every tool is runnable
  as `python3 -m frendsgen.diagram.<tool>`. No `sys.path` tricks, no imports that
  only work from one working directory.
- Layout and emission are two separate, importable functions. Layout takes the
  spec — nodes `{id, shape, label, parent, attached_to?}`, flows
  `{id, source, target, label}` — and returns **only geometry**, keyed by the ids
  it was given: a box per node id, a waypoint list per flow id. It never
  allocates, rewrites or drops an id.
- Layout needs nothing beyond the standard library, so that generating an export
  does not require `lxml`. Parsing tools (extract, validate, render) may.
- The shape vocabulary and sizes live in one table that a test can compare with
  the export side's table.

## 8. Round-trip the whole corpus

Rebuild every extracted spec and check three things: does the generator accept
the spec, do node ids / element kinds / flow pairs / nesting match the original,
does the validator pass.

Be honest about what each proves. The structure check is **weak** — the spec
stores exactly those fields verbatim, so a pass mostly proves nothing was
dropped. What the round-trip genuinely exercises is the layout engine, against
processes far messier than anything you'd hand-author. Every layout bug in the
Appendix was found this way and only this way.

Do not report round-trip success while step 3's unknown-type list is non-empty.

## 9. Verify, in this order

1. **Open it in bpmn.io** — the uploaded viewer through Chromium if you have it,
   otherwise ask the user to open the file at demo.bpmn.io. Nothing else settles
   rendering. Every geometry rule you derived is inference until a real renderer
   agrees.
2. **Render the SVG to PNG and look at it.** Overlapping labels, arrows ending in
   empty space, edges crossing shapes — obvious by eye, invisible to a passing
   validator.
3. **Run the validator.** It only checks the rules it has. When it reports zero
   errors, ask what the rules don't look at.

## 10. Extending

Adding a shape is three edits: the Type→name mapping in the extractor, the
name→(element, size, extra child) mapping in the generator, and the size and
cardinality tables in the validator. Re-run the round-trip and confirm the corpus
still passes.

Catch is the gap most likely to matter — error handling appears in nearly every
production integration, and the docs describe its behaviour without naming its
BPMN element. Determine it from the corpus and add it. If your only Catch
knowledge is doc-derived, label every Catch-bearing example as unverified.

## 11. Deliverables

Into `scripts/` of the skill, and nowhere else:

- `frendsgen/diagram/` — the package described in step 7.
- `docs/CALIBRATION.md` recording every validator rule that was changed and what
  drove the change; `docs/MEASUREMENTS.txt`, the raw output of the measurement
  script; `docs/CONSTRAINTS.md`, the quoted doc constraints; `docs/NOTES.md`, the
  two non-Frends cross-references.
- `examples/` — one hand-authored diagram spec that exercises the shapes the
  corpus lacks, marked as doc-derived.
- A section for `scripts/README.md` stating what was measured from which corpus
  and what has never been checked against a real renderer. No measured constants
  in it beyond naming the corpus they came from.

Do not ship the extracted corpus, regenerated files or PNGs: they are
reproducible, and a skill is loaded by people who will not want 5 MB of SVG.
Do not touch `SKILL.md` or `references/`; the export build writes the one
reference file that describes this tool.

---

# Appendix: what measuring won't tell you

No numbers here on purpose — derive those from the corpus in front of you. These
are the traps.

## Three mappings that mislead

- **Assign Variable and Code Task share `ElementParameters.Type` 12.** Both are
  `scriptTask`. The only discriminator is DI width — the small square is Assign
  Variable, the full-size box is Code Task. Check bounds, not element names.
- **`businessRuleTask` is Shared State Task, not DMN**, despite the name
  (`SelectedTypeId` is `AddOrUpdate` / `TryGetValue`).
- **Throw and Intermediate Return are the same element**,
  `intermediateThrowEvent` with a `signalEventDefinition`, and both are terminal
  in the XML with zero outgoing flows — even Intermediate Return, which continues
  executing. Nothing in the export separates them: `SelectedTypeId` does not
  (the `HttpResult` ones are labelled "Throw an error… return 500"). Record the
  ambiguity in the spec rather than guessing.

Also: unlabelled sequence flows have no `ElementParameters` entry at all, so a
missing entry is normal and not an error.

## The XSD ordering trap

Inside a `subProcess`, `loopCharacteristics` must come **before** the flow
elements. It belongs to the base `tActivity` type while `flowElement` is added by
`tSubProcess`, and in an XSD extension the base sequence comes first. Real Frends
gets this right.

Getting it backwards produces XSD-invalid nesting that renders fine and passes
any geometry-only validator. On one run, 49 of 77 regenerated files were declared
clean before a child-ordering rule existed; adding it turned them all red. This
is the clearest case of a green check measuring the validator rather than the
output — write the rule.

## Layout bugs to expect

Each produced a diagram that looked plausible until a validator or a human looked
closely.

- **Per-rank centring bends the main path.** Centring each column independently
  makes a single successor land on a different row than its predecessor.
- **A gateway's vertical drop can pass through an unrelated shape** in the same
  column on the target's row.
- **The gutter left of a target is not always empty.** Offsetting from the
  target's own left edge lands inside the column when a small shape is centred in
  a column sized by a wider neighbour.
- **Long same-row hops draw straight through everything between** when the flow
  skips several ranks.
- **A fallback corridor running below every shape escapes its container box**,
  because container sizes are computed before routing. Prefer corridors near the
  source row.
- **Small-shape labels collide** with a neighbouring event's label when placed
  below. Put them above.
- **Per-band row allocation sprawls vertically** — every branch gets a full row
  even when its only content is a hanging terminal. See the placement note in
  step 7.
- **Stacked hanging terminals force six-waypoint detours** on the flow to the
  lower one. Side by side, not stacked.
- **A Catch's handler lands to the left of the shape it guards**, because a Catch
  is off-grid and its successor ranks as a root. Rank Catch successors from the
  shape the Catch is attached to.

The shipped public templates contain a related defect worth recognising: a few
top-align a small shape with its full-size neighbour while docking its flows at
the row centre, so the arrow visibly ends in empty space beside the box. If your
own output does that, it's the centring bug above.
