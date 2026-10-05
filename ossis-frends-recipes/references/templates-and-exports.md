# Templates, Process Exports, and JSON Conversions

Sources: `https://docs.frends.com/reference/process-development/template.md`, `https://templates.frends.com`, `https://github.com/FrendsPlatform/FrendsTemplates` (templates under `/Templates`, arranged category → source system; each has `process.json`, `metadata.json`, `long-description.md`, `assets/`). The JSON-shape knowledge below was **verified empirically**: a public template imported into a Tenant, a Process created from it, and the resulting export diffed against the original template.

## Templates in the product

A Template = versioned snapshot of a Process (flow, shapes, config, Process Variables) used as a baseline for new Processes. Two purposes: (1) development reuse in the Control Panel — one Template as source of truth for many Processes, with "Update Processes" to propagate a new version and divergence tracking; (2) the BAP Integration Catalogue for business users. Both Processes and Subprocesses can become Templates.

Official flows: create from a Process ("Update or Create a Template from Process" in the Process list; set name, major.minor version, description, Template tags, Process tags for derived Processes, Process Variable defaults); import from `.json` file; create Process from Template (fills name/tags/variables); versioning with changelog; export to file.

Via Platform API once the template exists in the Tenant:

```http
POST /api/v1/process-templates/{templateId}/create-process
```
```json
{
  "name": "My Process",
  "description": "Created from template",
  "ignoreProcessTags": false,
  "processVariables": [
    { "name": "ApiKey", "value": "\"secret-or-env-reference\"",
      "isSecret": true, "mode": "text", "description": "API key" }
  ]
}
```

## The #var vs #env portability rule (most important design point)

Public templates are built for portability: configuration lives in **`#var.*` Process Variables**, `RequiredEnvironmentVariables` is `[]`, and configurable values sit in the outer `ProcessVariablesJson`. Tenant-local process exports are the opposite: lots of `#env.*` references, populated `RequiredEnvironmentVariables`, usually `ProcessVariablesJson: null`. **To make a production Process into a good reusable template, first replace tenant-specific `#env.Some.Variable` references with `#var.ApiBaseUrl`-style Process Variables and populate defaults** — otherwise the target Tenant must already have identical Environment Variables. The official Template docs endorse exactly this pattern (users can later promote the values to Environment Variables in their own Tenant).

## ProcessExport JSON shape

```json
{
  "Processes": [ { "...29 process fields..." } ],
  "LinkedTasks":      { "<process-guid>": [ "...task package refs..." ] },
  "LinkedSubProcess": { "<process-guid>": [ "...subprocess refs..." ] },
  "Version": "Acc41"
}
```
One export file can contain many Processes. Key process fields: `Name`, `UniqueIdentifier`, `Bpmn`, `ElementParameters`, `TriggersJson`, `UsedTasksJson`, `RequiredEnvironmentVariables`, `ProcessVariablesJson`, …

## Template JSON shape

```json
{
  "ProcessTemplates": [ {
    "Name": "...", "Modified": "...", "Modifier": "...",
    "Tags": [], "TemplateProcessTags": [],
    "Description": "...", "Version": 1,
    "UniqueIdentifier": "<template-guid>",
    "ProcessVariablesJson": "{...}",
    "ProcessInfo": {
      "Process": { "...same fields as an export's process..." },
      "LinkedTasks": { "<inner-process-guid>": [ "..." ] },
      "LinkedSubProcess": {},
      "Version": "Acc41"
    }
  } ]
}
```
A template = **metadata wrapper + one embedded process-export object**.

## Converting Template → ProcessExport

```
ProcessTemplates[0].ProcessInfo.Process        -> Processes[0]
ProcessTemplates[0].ProcessInfo.LinkedTasks    -> LinkedTasks
ProcessTemplates[0].ProcessInfo.LinkedSubProcess -> LinkedSubProcess
ProcessTemplates[0].ProcessInfo.Version        -> Version
```
**Extra step:** if the outer `ProcessVariablesJson` exists, copy it into `Processes[0].ProcessVariablesJson`, or a raw process import loses the template's variables. Caveat: importing into the same Tenant can collide on `UniqueIdentifier`; if you regenerate the process GUID, also re-key `LinkedTasks`/`LinkedSubProcess` from old GUID to new.

Prefer the official flow when possible: Control Panel → Templates → Import from file → Create Process from Template → fill variables → save/deploy.

## Converting ProcessExport → Template

Wrap ONE selected process:
```
Processes[i]        -> ProcessTemplates[0].ProcessInfo.Process
LinkedTasks[guid]   -> ProcessTemplates[0].ProcessInfo.LinkedTasks[guid]
LinkedSubProcess[guid] -> ProcessTemplates[0].ProcessInfo.LinkedSubProcess[guid]
Version             -> ProcessTemplates[0].ProcessInfo.Version
```
Add the metadata wrapper (Name, Modified/Modifier, Tags, TemplateProcessTags, Description, Version, new template GUID, ProcessVariablesJson). And per the portability rule above: don't just wrap a production process — move `#env.*` config into Process Variables and populate `ProcessVariablesJson` first.

## The two import paths validate differently

Observed by importing generated files into a Frends 6.x Tenant; none of it is in the docs, and the public templates cannot show it because they are all Template exports.

| Field | Template import | Process import |
|---|---|---|
| `Process.GraphJson` | `null` (as in all 77 public templates) | must be present and **empty string** `""`. `null` fails with a not-null error on `Process.GraphJson`; `"{}"` fails with "Old frends 4.2 type Processes are not longer supported". |
| `Modifier` | `null` accepted | must be non-null (`Value cannot be null. (Parameter 'modifier')`) |
| `UsedTasksJson` GUID casing | UPPERCASE | lowercase |
| Process Variables | outer wrapper `ProcessVariablesJson`; inner is `null` | on the process record itself |

So the Template → ProcessExport conversion above needs three more steps than the field moves: set `GraphJson` to `""`, make sure `Modifier` is non-null, and lowercase the GUIDs in `UsedTasksJson`.

**Task GUIDs are per-installation.** The GUID in `SelectedTypeId` (`/ProcessTask/<guid>/v1`), `UsedTasksJson` and `LinkedTasks[].Id` identifies a task *in one Tenant*. The same `Frends.HTTP.Request` has a different GUID in the public templates than in any given Tenant, so an export is not portable between installations as a file. `LinkedTasks[].PackageId` is the only place the task is named in words — match on that when moving a Process, never on the GUID.

## Working with exports as an assistant

Focus on `ElementParameters`, `TriggersJson`, `UsedTasksJson`, `ProcessVariablesJson`, `RequiredEnvironmentVariables` — that's where the reviewable substance is (parameters, expressions, variable and reference usage). **Do not hand-write or hand-edit the `Bpmn` XML field**: LLMs handle BPMN XML poorly, and the functionality lives in the parameters anyway. To see an export, draw it (`scripts/`: `python3 -m frendsgen picture export.json`). To produce one, generate it from a spec — see `process-generation.md`. For a structural change to an existing Process outside the generator's scope, describe the shape-level change for the user to make in the Process Editor.
