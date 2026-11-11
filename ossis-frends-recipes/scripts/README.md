# frendsgen

One package, two entry points, one layout engine.

- **`frendsgen generate`** turns a YAML spec into a `process.json` that Frends imports as a working Process: diagram, shape parameters, trigger, task bindings, Process Variables.
- **`frendsgen.diagram`** turns a spec into a Frends-style `.bpmn` picture, validates and renders `.bpmn` files, and re-derives Frends' drawing conventions from a corpus of real exports.

```
# importable Process
python3 -m frendsgen generate examples/order-sync.yaml -o process.json --tasks-from an-export-from-your-tenant.json
python3 -m frendsgen generate examples/order-sync.yaml -o template.json --form template
python3 -m frendsgen generate examples/all-shapes-6.3.yaml -o all.json --subprocesses-from an-export.json
python3 -m frendsgen validate process.json
python3 -m frendsgen lift     export.json --spec -o my.yaml     # real export -> editable spec
python3 -m frendsgen picture  export.json -o out/ --check       # any export or .bpmn -> SVG

# diagram only (not importable)
python3 -m frendsgen.diagram.generate examples/order-sync.diagram.json out.bpmn
python3 -m frendsgen.diagram.validate out.bpmn
python3 -m frendsgen.diagram.render   out.bpmn out.svg

# re-derive everything from a corpus
python3 -m frendsgen selftest /path/to/FrendsTemplates -v
python3 -m frendsgen.diagram.extract        /path/to/FrendsTemplates work/
python3 -m frendsgen.diagram.discover_types /path/to/FrendsTemplates
python3 -m frendsgen.diagram.measure        work/raw
python3 -m frendsgen.diagram.roundtrip      work/spec work/raw work/gen
python3 -m tests.test_generator
```

Run from this directory. `generate`, `validate` and `lift` need only Python 3 (PyYAML for YAML specs); `picture` and the `diagram` validate/render/extract tools also need `lxml`.

## Task GUIDs: bring your own

A task GUID identifies a task in **one installation**. The same `Frends.HTTP.Request` can have a different GUID in a Tenant than in the public templates. This package ships only the public templates' GUIDs; where the target Tenant holds the Task under another GUID, export any Process that uses it from that Tenant and pass it with `--tasks-from`; bindings are read from its `LinkedTasks` by `PackageId`. Nothing tenant-specific is stored. `lift` and `selftest` learn bindings the same way from whatever files they open.

## Architecture

`plan.py` builds **one node list** and allocates every BPMN id exactly once. It then hands that list, keyed by those ids, to `diagram/generate.py:build_layout()` — the same engine the diagram generator uses — and gets back only geometry. `emit.py` makes **one walk** over the list and writes each node's BPMN element, `ElementParameters` entry and `BPMNShape` in the same step, all reading the id off the same object. The two representations cannot drift apart by construction, and `validate.py` tests for it from outside anyway.

Two validators, two jobs: `frendsgen/validate.py` checks the export (envelope, id agreement, task payloads, `#result[...]` name resolution); `frendsgen/diagram/validate.py` checks geometry. Both were calibrated on untouched Frends output before being trusted on generated output — a rule that fires on a real Frends file is a bug in the rule.

The spec-level model is a tree of sequences; the layout engine handles arbitrary graphs. That is why the diagram side can draw all 77 public processes and the export side can express 7 of them.

## Scope

Importable, legacy form (default): Manual Trigger, `Frends.HTTP.Request`, Assign Variable, Code Task, Exclusive Decision (branches terminate or merge back to the next step), Foreach, While, Return, Throw, Process Variables. A construct is in this scope only when the corpus has enough real instances to rebuild it byte for byte.

Importable, `target: "6.3"`: every other documented shape and all twelve Triggers, rebuilt from a reference export made in the Frends 6.3.2 Process Editor (`tests/fixtures/shapes-6.3.json`, scrubbed of tenant identifiers; its README describes the four constructs it does not place). Lifting the reference export and regenerating it reproduces every shape's `ElementParameters` entry by Id and the same BPMN graph. The queue and hub Triggers need real connection settings before they activate. Subprocesses bind by name from the target Tenant's `LinkedSubProcess` (`--subprocesses-from`), the same way task GUIDs do.

Still refused by name: other Tasks, Shared State operations other than `AddOrUpdate`, `#env` closure, promoted values, artifacts in an importable file. The diagram side draws everything, artifacts and cycles included.

## What is tested, and what each test proves

| Check | Result on the 77 public templates | Proves |
|---|---|---|
| `selftest` calibrate | 0 errors, 2 warnings (the corpus's own two outliers) | the export validator does not misfire on real output |
| `selftest` rebuild | 82/82 HTTP Request payloads byte-identical | the task schema; the answer key is Frends output, so it is not circular |
| `selftest` lift | 7 of 77 fit the model; 7 regenerate identically | **7 of 77 is the honest coverage number** |
| `diagram.roundtrip` | 77 accepted, 77 matched, 77 validator-clean | the layout engine on real, messy graphs. The structure match is weak: the spec stores those fields verbatim |
| `tests.test_generator` | 26 pass | the import-path rules stay fixed, and on the 6.3.2 reference export: validator reports nothing; lift + emit rebuilds every shape entry by Id (HTTP Request entries skipped: the generator writes the templates' HTTP Request) and the same BPMN graph; lift -> YAML -> generate keeps every entry; the DMN builder rewrites the editor's XML up to its random ids; the `SKILL.md` description parses to the pinned text |
| `diagram.roundtrip` on `tests/fixtures` | 1 accepted, 1 matched, 1 validator-clean | the layout engine on the 6.3.2 shapes and the Catch wiring |

Format findings: `../references/process-generation.md` and `../references/templates-and-exports.md`. How each geometry rule was arrived at: `docs/CALIBRATION.md`, `docs/MEASUREMENTS.txt`, `docs/CONSTRAINTS.md`, `docs/NOTES.md`.
