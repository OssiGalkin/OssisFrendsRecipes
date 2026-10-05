I want you to build a Frends skill. I want you to be able to answer how to
do integration work, and modify and review processes, APIs, and other
integration solutions. 

1. **Core skill from live docs**: Fetch `docs.frends.com` and
`tasks.frends.com`, including glossary/integration pages and a representative
 task page. Recreate vocabulary, core concepts, shapes, triggers, tasks,
`#` references, Handlebars syntax, error handling, architecture, task
catalog usage, C# patterns, and live-doc fetching guidance.

2. **Custom Tasks section**: Fetch the custom task creation docs, the current
`.NET 8` template (`FrendsPlatform/FrendsTaskTemplate`), and the legacy
template (`CommunityHiQ/TaskTemplate`). Recreate scaffold commands, static
method structure, parameter-class conventions, attributes, XML docs, 
packaging/install steps, and clearly mark legacy template guidance as
maintenance-only.

3. **API Management vs API Portal add-on**: Fetch the built-in API Management
docs on `docs.frends.com` (OpenAPI-based API definitions, API Policies,
supported auth methods, Gateway Agent) — this ships with every tenant, 
no add-on required. Separately, fetch `docs.frends.com/api-portal` subpages
for the API Portal add-on. Recreate both, keeping them clearly distinct:
API Management is how you expose and secure a process as an API; API Portal
is a separate purchasable product for publishing that API to external
developers (concepts, roles, publishing flow, token/auth mechanics, audit log,
white-labeling).

4. **Business Automation Portal / BAP add-on**: Fetch `docs.frends.com/bap`
subpages. Recreate concepts, developer template-tagging flow,
business-user workflow, Organizations configuration, Shop Configuration, 
auth, and roles.

5. **Platform internals**: Fetch live docs for technologies, high availability, scalability,
data encryption, and integration lifecycle. Recreate technology stack, 
HA requirements, scaling axes, versioning, and security. Avoid stale-prone
sizing numbers unless directly sourced from current official docs.

6. **Monitoring & Operations**: Fetch the monitoring/operations docs
on `docs.frends.com`. Recreate the Process Instance list, per-shape
logging options, Promoted Values, Monitoring Rules, and the operational
dashboard — this is the "review and operate a running process" half
of the skill, distinct from the "build a process" half covered in step 1.

7. **AI Connector**: Fetch the Intelligent AI Connector docs on
`docs.frends.com` (this is the core reason for the skill, so don't let it fall
 out as an implicit side effect of step 1). Recreate what it is (a native BPMN task — AI as a step inside a
process, not a controller of it), the typical pattern (trigger → 
AI Connector → gateway routing on the result), the design intent (every
AI action logged as part of the execution trace, human approval checkpoints as
ordinary process shapes), and current roadmap items clearly separated 
from what's actually shipped (AI Connector v2 / ReAct-style loops, AI Toolbox, AI Cortex).

8. **Existing Tasks**: Fetch `https://tasks.frends.com` and
`https://github.com/FrendsPlatform/`, and learn how to fetch
relevant task information — docs and sources — when needed. You might not
always need the latest version.

9. **Processes and Templates**: After the previous steps, learn how
Frends processes are actually made. Fetch `https://templates.frends.com/` and
`https://github.com/FrendsPlatform/FrendsTemplates/tree/main/Templates`.
Use the Appendix below to understand the difference between a Process export
and a Template export. The appendix was built by importing public templates 
into a Frends tenant, creating processes from them, and comparing the
resulting process export against the original template — not from 
private/tenant-only documentation. Use it to verify that what you've
learned from the public template repo holds true in practice. Be especially
mindful of parameters and how variables and references are used in a process.
Do not focus on BPMN XML too much — it is not something LLMs are good at.

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