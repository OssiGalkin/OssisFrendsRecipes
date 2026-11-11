# AI Connector & Agentic AI

Built for Frends 6.3.x from: `/reference/shapes/activity-shapes/ai-connector`, `/reference/triggers/mcp-trigger.md`, `/frends-development/agentic-ai.md`, `/frends-development/agentic-ai/model-context-protocol.md`, `/release-notes/frends-6.3/version-6.3.0.md` and `/release-notes/frends-6.3/new-features.md` (search excerpts), `/reference/frends-platform-api/platform-api-reference/models.md` (`NativeAi` element type), `/reference/architecture/agent-application-settings.md` (`NativeAiSettings`), `/get-started/frends-glossary.md`.
The Frends MCP **server** that AI assistants connect to is not covered here; it belongs to `references/mcp.md` where that file is present (it is written by a separate build, not yet run for this snapshot). This file covers the platform features: the AI Connector shape and the MCP Trigger.

## Names

The shape's reference page is titled **AI Connector**; the docs section and older pages call it the **Intelligent AI Connector**. In exports its element type is `NativeAi`.

## What it is

An activity shape — AI as a step inside a Process, which keeps control of when it runs, what data it gets and what happens to the result. Typical shape: Trigger → gather data → AI Connector → decision routing on the result → deterministic handling. The docs' Agentic AI page frames agentic use for problems where the right sequence of actions depends on context not known at design time.

## Shipped vs roadmap (as captured for 6.3.0)

- **Shipped in 6.3.0** (release notes): the AI Connector can be configured to use **MCP Tools** — tools published by Frends Agents and by external MCP servers; reasoning steps became opt-in; the Process Editor supports **MCP Triggers**; improved visualisation of Long-running Process state.
- The AI Connector "becomes agentic when Tools are configured on it": with at least one Tool source it fetches the tool list and enters a reasoning loop instead of producing one response (Model Context Protocol page).
- MCP works both ways: Processes exposed as tools (MCP Trigger), and the AI Connector consuming tools from Frends and external sources.
- The 6.1-era AI Connector page described API calls inside the AI step and Computer Use as **future roadmap**. Treat any roadmap name (such as "AI Toolbox") as unshipped unless the current release notes say otherwise; name the version your answer reflects.

## MCP Trigger

- Each Agent is an independent MCP server at `/mcp` (JSON-RPC over HTTPS; `tools/list`, `tools/call`). `tools/list` returns only tools the caller may use.
- Fields: `name` (tool identifier; unique across activated Processes in the Tenant; also the endpoint identifier in the API Policy), `title`, `description`, `inputSchema`, `outputSchema` (enables "Create Return Shape"), annotations `readOnly` / `destructive` / `idempotent` / `openWorld` (hints only).
- Auth: external clients need a token with an **`mcp_tools`** claim (`"*"`, one name, or an array), issued via a Private Application or OAuth application and granted through an API Policy. AI Connectors in the **same Agent Group** bypass this authentication (internal call).
- Reference values: `#trigger.data.tool`, `#trigger.data.arguments.<name>`. The same page also says `inputSchema` gives autocomplete for `#trigger.data.body.*` — it contradicts its own reference-value section; prefer `arguments` and verify in the editor.
- `#trigger.type` has no documented value for MCP Trigger (the Trigger page's table omits it).
- `NativeAiSettings` (Agent): `FrendsAiClientTimeoutSeconds`, `FileDownloadClientTimeoutSeconds`, both default 100. From 6.3.1 `EnforceServerCertificateForNativeAiDownloads` controls TLS validation for file URLs in AI Connector parameters.

*Below re-checked this run against `/reference/shapes/activity-shapes/ai-connector` (full read). The `/guides/ai-features/` guides were deliberately skipped (how-to walkthroughs; the reference page covers the options); the 'Recipes' list names them only. In the page's GPT-4 custom-options table `temperature` is 0.0–1.0, while the Temperature field itself is 0.0–2.0 — both on the same page. Model lineup changes; check Administration > Frends AI Models.*

## Configuration essentials

- **Placement:** connected between Trigger and Return/Throw like any Task; Catch and Intermediate Return can attach.
- **Prompts:** System prompts (one or more; Frends provides a built-in system prompt that formats output like a standard Task `#result` — overridable/extendable) + User prompt (the operation + the data: **the AI receives NO Process data automatically; you must put it in a prompt**). Guide: "How to provide data to AI Connector".
- **File attachment:** absolute local path, HTTP(S) URL, or Base64 data URL; types image/text/audio, auto-inferred.
- **Service types:** **Frends AI** (Frends-hosted Azure AI; data processed in Frends' cloud, not on your Agent — relevant for data-sovereignty reviews; usage metered in **Frends Credits**); **Azure Inference** (your own service — note it's the *Azure AI Inference API*, NOT Azure OpenAI Service, which is unsupported); **Ollama** (on-prem). Non-Frends services need Service URL + API key.
- **Frends AI models** (currently GPT-5-family): "GPT - General World Knowledge" (GPT-5), "Image Processing" (GPT-5-Mini), "Data Classification" and "Data Extraction" (GPT-5-Nano). Enable/disable at Administration → Frends AI Models. Model lineup changes often — verify live.
- **Tuning:** Temperature (0–2) + TopP, or Custom options JSON. GPT-4-era keys: `response_format`, `temperature`, `top_p`, `frequency_penalty`, `presence_penalty`, `max_tokens`, `seed`. GPT-5-era keys: `reasoning_effort` (`none`/`medium`/`high`), `response_format`, `max_completion_tokens`, `seed`. JSON response format requires the word "json" in the prompt.
- **MCP setup:** select Tools from your Tenant's MCP Triggers and/or add external MCP servers (address, friendly name, auth JWT, optional one-time discovery token for Fetch Tools). Tool allowlist can also be a JSON array like `["Frends::get_invoice_details", …]`. Local MCP Tool calls go over localhost inside the Agent/Agent Group and **bypass MCP API Policy auth** (full access — mind this in reviews); external servers are called over HTTPS from the Agent. The AI service never touches your MCP tools directly — the Agent brokers all calls.
- **Logging toggles:** "Include reasoning in response" (off by default, saves tokens), "Skip logging result and parameters", "Promote result as".

## Result shape

An AI Connector's tool list names MCP-Trigger Processes as `Frends::<tool name>` (stored as `{"mode": "list", "value": "[\"Frends::<tool name>\"]"}`). Within the same Agent Group no Private Application or API Policy is needed; the tool Process must be deployed and active. Outside the Agent Group, or from an external MCP client, a token with an `mcp_tools` claim is required. `#result.Response` (the docs say string, but with the Frends system prompt it can be a JSON object, so `(string)#result[X].Response` fails; read it as `(JToken)#result[X].Response`. With the Frends system prompt it's JSON containing a `Response`-like answer field — field name can vary by prompt, e.g. `Category` — and `Reasoning` string array when enabled). `#result.ToolCalls` (JArray of `{ToolName, CallId, Arguments, Result, Error}`). `#result.Metadata` (token counts, Frends Credit usage). Cast with `(JToken)#result[AI Connector].Response` and read fields from it; `JObject.Parse` of a string applies only where Response really is a string.

## Recipes in the guides

Semi-deterministic AI Processes (AI reasoning + Process control flow), reusable AI agents as Subprocesses, simple RAG as a standard Process, tokenizing/masking data before sending to AI, on-prem Ollama and Azure AI Inference setup, fine-tuned models.
