# Platform internals — Agents, configuration, deployment, versions

Built for Frends 6.3.x from:
`/reference/architecture/agent-application-settings.md`, `/reference/process-development/process.md`,
`/reference/frends-platform-api/platform-api-reference/process-deployments.md` and `models.md`,
`/reference/shapes/activity-shapes/shared-state-task.md`, `/reference/triggers/http-trigger.md`,
`/reference/administration/environments-and-agent-groups/agent-groups` (full read),
`/management-and-operations/integration-lifecycle/deployment-pipeline`, `/hybrid-integration-architecture/high-availability`, `/guides/setup-and-installation/how-to-set-up-high-availability-configuration`, `/hybrid-integration-architecture/technologies`, `/guides/setup-and-installation/configuring-ssl-certificates-for-frends-agent`, `/management-and-operations/maintenance-and-support`, `/security/integration-security` (search excerpts),
`/release-notes/frends-6.3/version-6.3.0.md` (search excerpt), `/release-notes/frends-6.3/breaking-changes` (full read), `/reference/architecture/technical-details-for-frends-agent` (full read), `/hybrid-integration-architecture/deployment-models` (full read), `/hybrid-integration-architecture/technologies` (full read), `/security/data-encryption` (full read), `/security/firewall-management`, `/reference/architecture/agent-connectivity-requirements`, `/guides/setup-and-installation/installing-frends-agent`, `/guides/setup-and-installation/performing-frends-version-update` (search excerpts), `/guides/general/frends-best-practices-collection.md` (search excerpt).

**Not read this build:** Updating from Legacy Frends and Updating Agent Certificates (the certificate-overwrite behaviour is covered from the settings page). **Out of scope by design** (router rule): Recovery from Disaster (RPO/RTO), Compliance, sizing — fetch live or say so; never from memory.

## Runtime and target framework

- A Process is converted to C# and compiled with .NET; it runs in its own execution context inside the Agent's .NET runtime.
- **6.3.0 release notes:** UI and Log Service run on .NET 10; **Processes are compiled to target .NET 10**; the cross-platform Agent runs on .NET 10; on-premises cross-platform Agents need .NET Runtime 10.0.5 or newer. **From 6.3.1 the requirement is .NET Runtime 10.0.7 or newer** (6.3 Breaking Changes); the Windows Agent and the Management Web Portal need the **.NET 10 hosting bundle**; Cloud Agents and Compliant Cloud images include .NET 10. (6.1.x required .NET Runtime 8.0.21+.)
- **Out of date against that:** the Technologies page ("targets primarily .NET 8", runtime 8.0.15+) and the Installing Frends Agent guide (".NET 8.0 and ASP.NET Core 8.0 runtime"). Use the Breaking Changes page for the version you install.
- The Process reference page still calls .NET 8 "the current default target framework" — out of date against the 6.3.0 release notes. .NET Framework 4.7.1 serves legacy environments; .NET Standard 2.0 exists for migration and gets no new development.
- Deployment validation (Platform API): the Process target framework must match the Agent Group framework.
- Agent Groups are cross-platform or not (`isCrossPlatform`: Agents installable on Windows and Linux; containers on Linux, Kubernetes, Docker).
- Rebuild Process (Process list) recompiles — occasionally needed after a Frends or target-framework upgrade.

## Agent configuration files

Read in this order, later overriding earlier:
1. `appsettings.json` 2. `appsettings.production.json` 3. `secrets/appsettings.secrets.json`

- `appsettings.json` and `secrets/appsettings.secrets.json` are **overwritten on install**; lasting changes go in `appsettings.production.json`, which you create manually next to `appsettings.json`.
- Changes apply on Agent **restart**; no reinstall needed.
- `CertificateThumbprintOrPath` (thumbprint from `CurrentUser\My` by default — `CertificateStore: LocalMachine` to switch — or a `.pfx` path with `CertificatePassword`): **updating the Agent overwrites this setting** unless the new settings file is edited. Empty → self-signed certificate (regenerated per container instance; not for production).
- Introduced in **6.3.1**: `EnforceServerCertificateForPreSignedUri`, `EnforceServerCertificateForNativeAiDownloads` (both default `false`), `EnableClientCertificateValidation` (`null` = ask for a client certificate only when an HTTP Trigger uses Certificate authorization; `true` always; `false` never; applies to new connections without restart).
- Other settings worth knowing: `AgentDatabaseConnectionString` (SQL Server, set in the Agent Group view, same for all Agents in the group) or `SharedStateStore` — **one of them is required for Schedule and File Triggers when the group has several Agents**; otherwise state stays in per-Agent SQLite. `DataDirectory` (container SQLite location — put it outside the container). `AzureServiceBusSasTokenConfiguration.UseAmqpWebSockets` or `RabbitMqConnectionString`. `LargeMessageStoreUri`: **messages that do not fit the message bus travel through this blob/file location**. `HttpLoggingOptions.HeadersToOmit` (default list includes `Authorization`, `Cookie`, `X-Api-Key`). `HealthCheckApiKey` (leave empty with Gateway Agents in the group). `GatewayTargetAddresses` makes the Agent a Gateway; `TimeoutMinutesForGateway` default 10. `MaxConcurrentRemoteSubprocessesPerCpu` default 64. `MaxDehydratedProcessDataSizeKb` (Checkpoint state) default 1024. `MaxSubprocessDepth` default 30. `CheckInstancesForZombiesRunningLongerThanMinutes` default 900. `EnableOTPLMetrics` / `EnableOTPLTracing` (OpenTelemetry via `OTEL_EXPORTER_OTLP_ENDPOINT`). `Storage__S3ObjectStorage__BucketPrefix` (new Tenants only; changing it loses step data).
- The settings page is versioned (`/reference/frends-6.2.0/architecture/…`, `/reference/frends-6.1.0/…`): read the one matching the Agent.

## Agent Groups, HA, Gateway

- All Agents in an Agent Group share a common database store and message bus and run the same Processes. Processes and APIs deploy to **Agent Groups, never to single Agents**.
- **Agent registration mode** (per group): **Self-Hosted Agent** (manual provisioning; locked once Agents are connected, until all disconnect), **Kubernetes Deployment** (pods self-register on first heartbeat and are removed when they terminate), **Kubernetes StatefulSet** (self-register; registrations kept across restarts). Deployment ↔ StatefulSet can be switched without disconnecting Agents.
- **Connection string** (group): SQL Server, Azure SQL or PostgreSQL, for shared state, distributed locks and operational messages; every Agent needs network access to it. Separate database installs: add `;TrustServerCertificate=True` unless the certificate is trusted. The Agent download menu includes the **Database Initializer** to prepare the shared schema before starting new Agents.
- Advanced settings: **Allow running test processes** (turn off in production) and **Cross platform** (changing it requires reinstalling/redeploying the Agents). **Legacy Agents will be discontinued in Frends 6.4**; the cross-platform Agent is the only type going forward.
- Agent downloads: preconfigured Linux binary package, Windows installer, Configuration only, Database Initializer. Containerised groups: "Download Kubernetes configuration" and "Default external address for new agents".
- **Synchronize agents** (button on the Agent Group view): sends an immediate synchronization signal to all active Agents in the group, forcing them to refresh deployment caches, reload active Process configurations and update Environment Variables **without a service restart**. That is all the page says — no page read states when synchronization otherwise happens automatically.
- **HA**: several Agents in one group need a **load balancer and a shared database**. Without a Shared State Store, only one predefined (not dynamic) **Primary Agent** runs File, Schedule and Conditional Triggers — possible but not recommended (Technical details for Frends Agent). The setup guide: an SQL database is highly recommended (a cluster avoids a single point of failure); HA without a shared database is possible but limited; HTTP/API traffic needs a load balancer or an API Gateway Agent; the license must allow enough Agents.
- **Gateway Agent / API Gateway**: proxies API traffic to executing Agents and runs no Processes; can sit in a DMZ while Agents stay internal.

## Deployment models

- **Self-hosted** (on-premises or your own cloud): Agents run as a service on your servers; connect to the Tenant over Azure Service Bus; API calls go straight to your Agents, not via the Frends cloud; **Agents keep executing if the Frends UI is unavailable**; Remote Subprocesses between Agent Groups are coordinated over the message bus, not direct connections. You own infrastructure, maintenance, updates and monitoring. The page's choice for strict data sovereignty.
- **PaaS / Frends Cloud**: Frends Support creates and maintains the Agents in the Frends cloud; geography and resource sharing depend on subscription tier; Tenants cannot access each other's data on shared resources.
- **Container**: Kubernetes, on-prem or cloud, mixable with other Agents; dynamic Agents can join and leave an Agent Group; StatefulSets keep Agents registered across downtime.
- **Hybrid**: any mix. Every Tenant starts with a PaaS Cloud Agent in the Development Environment. Kubernetes and HA depend on pricing tier and contract.

## Host requirements and connectivity

- Hosts (Installing Frends Agent): Windows 10, 11 or Windows Server 2019+; **Ubuntu Server 22.04 LTS+**; or Kubernetes/Docker. Service user in the local admin group. Linux runs only the cross-platform Agent. Legacy Agents need .NET Framework 4.7.2. SQL Server minimum **2017** for on-premise deployments (Breaking Changes).
- **Outbound** (Agent connectivity requirements, 5.7+): the Frends UI `yourtenant.frendsapp.com:443` (Agents fetch Process and Task packages through the UI); Azure Service Bus 443, 5671, 5672 — if 5671/5672 cannot be opened, add `;TransportType=AmqpWebSockets` to the connection string to use 443; Azure Blob Storage 443. HA with a shared database: outbound to the database (SQL Server / Azure SQL at least 1433).
- **Inbound**: none for normal operation — the Agent communicates outbound over TLS 1.2. Inbound only on the Agent's HTTPS ports for APIs/HTTP Triggers, or put a Gateway Agent in front (then only the Gateway needs inbound, and it must reach the backend Agents' ports).
- The Agent's cloud side is Azure or **Cleura**; its message bus is Azure Service Bus or **RabbitMQ**; blob storage Azure Storage or **Ceph** (Technical details).
- Message bus carries deployments, configuration (Environment Variables, API keys, OAuth settings), Process logs, heartbeats, Manual executions, and **Remote Subprocess requests between Agents in the same Environment**. Messages over **200 KB** go through the Agent Group's Large Message Storage blob container.
- Databases (Technical details): SQL Server / Azure SQL (configuration and shared state; SQL login or integrated security; `db_datareader`, `db_datawriter`, execute) and SQLite (log cache when the bus/storage is unreachable; cross-platform configuration store; shared state only without HA). The Agent Group page also accepts **PostgreSQL** connection strings — the two pages list different engines.
- **Cloud Agents have static public outbound IPs** that survive restarts, updates and scaling; self-hosted and private-cloud Agents use whatever your network provides.

## Encryption and data handling (Data Encryption page)

TLS 1.2 between on-prem Agents and the Frends cloud; HTTPS-only platform; data at rest AES-256 with keys in Azure Key Vault; a masked Task's input and output are not shown and not stored; Secret Environment Variables encrypted with AES-256 and not viewable again once secret; monitoring data retention configurable up to **60 days**, with **zero retention** possible per Process.

## Updating

- Control Panel first, then Agents one at a time, least critical first. PaaS Agents: Frends Support. Self-hosted cross-platform: stop the service, run the new installer. **Kubernetes: re-download the configuration — `Frends-Agent-Deploy.yaml` and the secrets files are version-specific**. Self-hosted Agents with an SQL database also need the **Database Initializer** schema update (Breaking Changes).
- 6.3 breaking changes worth knowing: **6.3.1** — StatefulSets created before 6.3.1 must be deleted with `--cascade=orphan` and re-applied (new per-pod volumes); `EnableClientCertificateValidation` tri-state; failed/denied requests audit-logged by default (`EnableAuditLoggingForFailedRequests`); Database Initializer always enables snapshot isolation. **6.3.2** — new Agent per-Process log category; S3 log retention via lifecycle rules. **6.3.3** — API Policy public access fix (see `api-management.md`); IPv6 allowlist matching; `TimeoutMinutesForGateway` now limits each wait, not the whole response.
- **Legacy Agent: Frends 6.4 is the first version without it.**

## Agent HTTPS certificate

Default: self-signed. **Windows**: install in the certificate store, paste the thumbprint into the Agent's "SSL Certificate thumbprint" in the Control Panel, and download the installer **after** setting it (the installer then sets `CertificateStore`). **Linux**: import the PFX with the bundled CertificateTool (`dotnet --roll-forward Major /opt/frends-agent-linux/CertTool/GSoft.CertificateTool.dll add -f <pfx> --password <pw> --store-name My`); store at `/opt/frends-agent-linux/.dotnet/corefx/cryptography/x509stores/my`. **Kubernetes** and direct PFX paths: see the guide. An Agent update overwrites `CertificateThumbprintOrPath` unless the new settings file is edited (settings page).

## Data location (Technologies page)

Azure hosts the Control Panel and orchestrates Agents, also for self-hosted Agents; Azure Service Bus connects Agents to the Control Panel. With self-hosted Agents Process data is handled mainly on your Agents, but **some logging options and Remote Subprocess executions can transfer data to the Frends cloud**. The AI Connector's Frends AI service processes data in Frends' Azure cloud (AI Connector page).

## Deployment (Platform API, `process-deployments.md`)

- `POST /api/v1/process-deployments`: up to 20 Processes to one Agent Group; `activateTriggers` (default **true**) separates *deployed* from *Triggers active*; per-Process `processVariables`. Validation: all used Environment Variables have values; all used Subprocesses deployed to the target; target framework matches the group.
- Activate / deactivate Triggers: `PUT` / `DELETE /api/v1/process-deployments/{id}/activation`. Run: `POST /api/v1/process-deployments/{id}/execute` (202 + Location). A Process cannot be undeployed from the Development Agent Group.
- In the UI: Activate/Deactivate per Process per Agent Group; **Switch version** rolls back or forward; Processes are created and edited only in the Development Environment.
- **New version over a running one** (Deployment Pipeline page): no downtime; ongoing executions finish on the version they started with; the old version keeps handling Triggers until the new one is ready, then takes new executions. A Process that was active stays active after deploying a new version. Roll back with **Switch version**.

## Shared State and storage

Shared State lives in the Agent Group's database; with per-Agent SQLite it is not shared between Agents, and SQLite under concurrency can lock — SQL Server is recommended for HA.

## Security pointers (Best Practices Collection, Integration Security)

- Avoid Remote Subprocesses in integrations or APIs with heavy traffic: extra overhead, reduced scalability (Best Practices Collection). No throughput figure is documented — do not invent one.
- Credentials in **Secret** Environment Variables; never log passwords, tokens or secrets (Best Practices Collection).
- HTTP Trigger Basic authentication is not supported on Cloud Agents; Certificate authorization is Windows-Agent-native, cross-platform Agents need client-certificate support enabled.
- Integration Security: secrets in Secret Environment Variables; never send a secret with its username or in clear text; validate URLs from user input (allowed schemes, no internal IP ranges); sanitise logged user input; mask production data used for testing; production logging and archiving of handled data recommended off; document what PII is logged, where, who can access it, and how it can be deleted.
