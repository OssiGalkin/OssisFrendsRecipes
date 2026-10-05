# Platform Internals — technologies, HA, scalability, security, lifecycle

Docs under `https://docs.frends.com/hybrid-integration-architecture/…` and `/security/…`. Avoid quoting sizing numbers (CPU/RAM/throughput) from memory — fetch `technical-details-for-frends-agent.md`, `agent-connectivity-requirements.md` or `scalability.md` live if asked.

## Technology stack

- **.NET 8 / C#**: everything — backend, Agents, and every Process/Subprocess/API is compiled to C# for execution. Legacy support: .NET Framework 4.7.1 and .NET Standard 2.0 (for legacy→cross-platform Agent migration); .NET 6 was replaced by 8 from Frends 5.7 onward. New Task development targets .NET 8 only. Current Agents need .NET Runtime 8.0.15+ on the host.
- **Newtonsoft.Json**: the de-facto data plane — essentially all Process data is JObject/JArray/JToken.
- **Azure Cloud**: hosts Control Panel, orchestrates Agents, runs PaaS Agents. Lower tiers = shared multi-tenant resources; higher tiers = private resources, vertical scaling, choice of geographic region. Self-hosted Agents still use the Azure-hosted UI/orchestration; Process data stays on your Agents, but some logging options and remote Subprocess execution can move data to Frends cloud — flag this in data-sovereignty reviews.
- **Azure Service Bus**: the Agent↔Control Panel channel. **Outbound-only connections from Agents** (no inbound firewall openings), encrypted and authenticated, reliable delivery when an Agent is temporarily offline. This is the key hybrid-security argument.
- **Azure AI services** power the AI Connector (Azure AI Inference API) and AI assistants; Ollama for on-prem AI.
- **BPMN 2.0 subset**: visual layer only. BPMN XML export/import exists but carries none of the C# functionality; imports from other tools rarely produce usable results. Real portability = Frends Process export / Template export (see templates-and-exports.md).
- **Docker/Kubernetes**: containerized Agents; horizontal scaling requires the Agent Group to be in HA configuration.

## High Availability

Standard setup: one Agent down = service blocked. **HA configuration** = multiple Agents in one Agent Group sharing executions; also the horizontal-scaling mechanism. **Requirements: a load balancer + a shared database** for coordination — without them, only the Primary Agent executes. Once set up, HA is invisible to developers: deployment targets are always Agent Groups, never individual Agents; the only visible trace is the "triggering Agent" column in the Process Instance list. Setup guide: "How to set up High Availability configuration".

## Scalability

Two axes: **vertical** (bigger PaaS tiers / bigger self-hosted machines, private Azure resources for heavy single executions) and **horizontal** (more Agents in an HA Agent Group; K8s orchestration for containers). Gateway Agents scale the API entry point separately from execution.

## Runtime & lifecycle

- **Frends Runtime / Process Execution Model** pages describe how Control Panel, Service Bus and Agents cooperate and how Processes execute; **Deployment Models**: full cloud PaaS, hybrid, on-prem, and combinations.
- **Integration Lifecycle** = built-in CI/CD: draft → deploy through Environments via the **Deployment Pipeline**; **Environment Variables** decouple config from logic; **Version Control** provides changelog + rollback for Processes, Subprocesses, APIs and Environment Variables (per-variable changelog shows who changed what, and which Processes use a variable).
- **Maintenance & Support** + **Recovery from Disaster** cover Frends-side monitoring and DR promises; version updates via "Performing Frends version update"; legacy migration via "Updating from Legacy Frends" (.NET 8 cross-platform Agents).

## Security

- **Data Encryption** page: encryption in transit and at rest; Environment Variable Secrets encrypted in DB and masked in UI; fetch live for audit specifics.
- **Integration Security**: securing Processes/Tasks (also linked from tasks.frends.com as the task-security note).
- **API Security Features**, **Firewall Management** (per-Agent access control), **Access Control** (RBAC), **Compliance** (GDPR-era, EU-hosted positioning), **AI Trust & Transparency** (AI governance, audit logs).
- Agent firewall needs: outbound-only, exact endpoints in `agent-connectivity-requirements.md`; data flows diagrammed in `frends-data-flowcharts.md`.
