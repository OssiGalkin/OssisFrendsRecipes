# Monitoring & Operations — reviewing and operating running Processes

Built for Frends 6.3.x from: `/reference/process-development/process.md`, `/guides/development/how-to-handle-errors-in-frends-processes.md`, `/reference/shapes/activity-shapes/task.md`, `/reference/administration/process-log-settings` (full read), `/management-and-operations/maintenance-and-support` (search excerpt), `/docs/frends-6.2.0/…/process-instances.md` and `/docs/frends-6.1.0/…/process-instances.md` (search excerpts), `/guides/general/frends-best-practices-collection.md` (search excerpt).
Also `/reference/administration/monitoring-rules`, `/management-and-operations/dashboard-and-monitoring/dashboard`, `/guides/integration-management/how-to-use-dashboard`, `/management-and-operations/dashboard-and-monitoring` and `/security/data-encryption` (search excerpts / full read). **Deliberately skipped:** System Logs and AI Audit Logs (pointer below only), User Management / RBAC, Audit Trail Log API.

## Process Instances

- One Process Instance per execution: inputs, per-shape results, return value. The Process Instance View shows the run visually; it is the main debugging tool.
- **Promote result as** (any shape's advanced settings): value gets its own column in the Process Instance list and is **always logged fully regardless of log level**. Promote small identifiers (order ID, customer ID, error code), not payloads.
- **Skip logging result and parameters**: logs show `<< Omitted >>`. For secrets, PII and very large data.
- **Dispose at the end of the scope**: frees a large result when its scope exits.

## Log levels

- Levels: **Only errors**, **Default**, **Everything**; plus "Log Process parameters and return value" and the Process Instance history retention period. "Log everything for" a Process can be set for up to 24 hours.
- Production recommendation (log settings page and Best Practices Collection): **Only errors**, parameters/return value off, the shortest retention you can live with.
- **Where they are set.** Process Log Settings: defined **per Agent Group**, overridable per Process ("Use Agent Group setting"), managed from the Process list for the Agent Group. The Process reference page instead calls it the "Environment-wide default" — older wording; the log settings page is the specific one.
- Only errors: no step or Subprocess data; failing Task/Subprocess parameters are logged with the exception; promoted results always logged. Don't promote results inside Subprocesses under Only errors (logged data you cannot view). Default: step results except Foreach elements; no input parameters. Everything: all parameters and results, untruncated.
- **Logged-data cap — the pages disagree.** The 6.1.0 and 6.2.0 snapshots of the Process Instances page: 100 array entries or **8192** characters on Default. The current Process Log Settings page: first 100 array elements, each value up to **10,000** characters. The current Process Instances page was not read in full; cite both and prefer the current log settings page.
- **Retention**: the Log Service deletes old Process Instances; **default 14 days**, settable per Agent Group or per Process (Process Log Settings); maximum **60 days**, and **zero retention** can be set per Process (Data Encryption, Maintenance & Support). An older pre-GitBook page said 60 days was the default; it is out of date.
- `#process.Logger` writes to the **Agent log**, not the Process Instance; Debug only on Everything, Information suppressed on Only errors.

## Error handling seen from operations

- Finish failure paths in **Throw** so instances show as failed; handled errors that return normally look like successes.
- **Subprocess to call on unhandled error**: last-chance reporting/cleanup after a failure (often a support ticket); Shared State can rate-limit repeated reports.
- **Monitoring Rules** (Administration > Monitoring Rules, per **Environment**; Administrator role or matching permission): inspect all executions in an Environment by **Promoted Values**. Optional value filter: `Exists`, `Contains` (C# `String.Contains`, no wildcards), `Greater Than` / `Less Than` (numeric values only), `Equals`. Alert if `Sum` / `Maximum` of values or `Count of instances` compares (greater, less, equal or not) to a threshold, over a time interval, with active days, time zone and holidays. Action: email, and/or run Processes whose Manual Trigger has **"Use for Monitoring Rules"** on; they receive `#trigger.data.monitoringRule` (e.g. `.variableName`, `.emailRecipients`). The classic use — alert when `Count of instances` of a "Success" value is `Less than 1` in 24 h — catches "the Process never ran", which per-instance handling cannot.

## Dashboard and platform logs

- **Dashboard** (profile menu, or `yourtenant.frendsapp.com/Dashboard`): widgets for successful and failed Process counts, a Process execution graph over time, and an errors list; filter by Environment, Process tags and time; widgets can be moved and renamed.
- **Agent event logs**: Administration > Environments, per Agent — connectivity failures and Trigger initialisation errors. **API connection logs** need a logging configuration in an API Policy (`api-management.md`). AI Audit Logs and System Logs have their own pages (not summarised here).
- From 6.3.1, failed and denied requests (4xx/5xx) are audit-logged by default; `EnableAuditLoggingForFailedRequests: false` restores the old behaviour (6.3 Breaking Changes).

## Operating actions (Process list)

Edit · **Run Once** (manual execution with input; logged as an instance) · Activate / Deactivate Triggers per Agent Group · Log settings · Deploy Process to Agent Group · **Switch version** (rollback/forward) · Rebuild Process · Copy · Delete · Export to file (`.json`) · Tag · Pin · Cleanup old versions · Update or Create a Template from Process · Unlink from Template · Show Process instances · Show changelog · Show Process documentation (AI documentation generation).
Process Editor actions: Import BPMN (shapes Frends doesn't support are dropped or simplified), Export BPMN XML (diagram only, no functionality), Save as picture (SVG), Diff between versions.
Platform API equivalents: `/api/v1/process-deployments/{id}/execute`, `/activation` — see `platform-internals.md`.
