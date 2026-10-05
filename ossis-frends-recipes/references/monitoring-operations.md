# Monitoring & Operations — reviewing and operating running Processes

This is the "operate" half of the skill (the "build" half is SKILL.md). Docs under `https://docs.frends.com/management-and-operations/…`, `/reference/administration/…`, guides under `/guides/integration-management/`.

## Process Instances (the core log)

Every execution = a **Process Instance**: when it ran, success/failure, duration, results, which Agent triggered it (visible per-row — the only place HA is visible). Open an instance to see the visual flow with per-shape logged values (inputs/outputs, durations, HTTP bodies/headers) — the primary debugging tool and readable by non-developers.

**Log levels** (Process Log Settings, per Environment/Process):
- **Errors only** — recommended for **production** (storage + performance).
- **Default** — results of each Task; fine for development. Data capped at **100 array entries / 8192 characters** per value.
- **Log everything** — inputs and outputs of every shape; turn on temporarily for debugging.

**Per-shape overrides** (Advanced settings on any shape):
- **Promote result as `<name>`** — value appears as its own column in the Process Instance list; searchable/filterable; **always logged fully regardless of log level**. Promote low-cardinality business identifiers (OrderId, CustomerId, error codes), never large payloads. Promoted Values + errors-only level is the standard production combo.
- **Skip logging result and parameters** — logs show `<< Omitted >>`. Use for secrets/PII and for very large payloads (performance).

## Monitoring Rules (fleet-level)

Administration → Monitoring Rules, defined **per Environment**. They inspect Promoted Values across all instances in a time window — data-centric monitoring that catches what per-instance error handling can't (including "the Process never ran at all"):
- alert if COUNT of instances with a Promoted Value < N per interval (e.g. <100 OrderIds/hour);
- alert if COUNT of matches > N (e.g. any promoted ERROR marker);
- alert on the VALUE itself (equal/greater/less, sum, max);
- active-time windows (e.g. only business hours).
Action: send email or trigger a Process.

## Dashboard & other views

- **Dashboard**: configurable widget view (executions, errors, throughput) per Tenant; guide "How to use Dashboard". Custom externals: Grafana dashboard guide and OpenTelemetry export from Agents.
- **API Monitoring**: all API connections incl. unsolicited traffic (see api-management.md).
- **System Logs**: Agent + OS-level logs; guide "How to access Agent logs"; crash-dump collection guide exists.
- **AI Audit Logs**: all AI usage in the Tenant.
- **Audit Trail Log API**: extra audit logging via Platform API.

## Operating actions

- **Manual execution** of a Process (also for one-off ops tasks); test single Tasks/Processes via "How to Test Processes and Tasks".
- **Bulk actions** on multiple Processes at once (activate/deactivate/deploy) — "How to perform actions to multiple Processes"; organize with **Tags**.
- **Deployment pipeline**: Processes move between Environments (Dev→Test→Prod) with built-in versioning; **Environment Variables** carry the per-Environment config so the Process itself is unchanged. **Version Control** view gives changelogs and rollback for content.
- **User management**: RBAC; roles like Editor; custom roles with granular permissions (e.g. `ApiPolicy.Edit`); details in Role-Based Access Control reference.
- **Frends Platform API** (must be enabled first — see "How to enable Frends Platform API"; Entra ID app registration + admin consent, coordinated with Frends Support): programmatic access to Processes, ProcessInstances, ProcessDeployments, EnvironmentVariables, ProcessTemplates, Agents, AgentGroups, ApiPolicies, Tags, etc. There's also an official **PlatformApi.Request Task** for calling it from Processes.
