# AI Connector & Agentic AI

Docs: `https://docs.frends.com/frends-development/agentic-ai.md` (+ `/intelligent-ai-connector.md`, `/model-context-protocol.md`), reference `https://docs.frends.com/reference/shapes/activity-shapes/ai-connector.md`, guides under `/guides/ai-features/`, audit at `/management-and-operations/dashboard-and-monitoring/ai-audit-logs.md`.

## Design philosophy — lead with this

The **Intelligent AI Connector is a native BPMN shape: AI as a step *inside* a deterministic Process, not a controller of it.** The Process remains the outer structure — it decides when the AI step runs, what data it gets, and what happens with the result. Typical pattern: **Trigger → (gather data) → AI Connector → Exclusive/Inclusive Decision routing on the result → deterministic handling**. Human approval checkpoints are ordinary process shapes (and since 6.2, Long-Running Process shapes let a flow dehydrate while waiting for approval). Every AI action is logged as part of the execution trace — decisions, tool calls, observations — in the same Process Instance log as everything else, plus tenant-wide **AI Audit Logs**. Use it for fuzzy/NLP steps (classification, extraction, generation), not to replace integration logic.

## Shipped vs. not shipped (re-verify in the release notes)

- **SHIPPED in Frends 6.3:** the agentic mode. AI Connector supports **MCP Tools** — from Frends' own MCP Triggers and from external MCP servers — with a reasoning loop: model picks a tool → Agent calls it → result returned to model → repeat until resolution or iteration cap. This is the capability earlier roadmap talk called "AI Connector v2 / ReAct-style loops". Also 6.3: MCP Trigger turns any Process into an MCP Tool; MCP works both directions.
- The toolbox is a hard permission boundary (AI can only call explicitly listed tools), reasoning depth is capped and configurable, and each step is in the execution log.
- Names like "AI Toolbox" / "AI Cortex" from older roadmap material: **do not claim these as shipped products** — check `https://docs.frends.com/release-notes/` before referencing them.
- Other shipped AI assistance (separate from the Connector): AI Task Configurator, AI Code Generator, Documentation Generation.

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

`#result.Response` (string; with the Frends system prompt it's serialized JSON containing a `Response`-like answer field — field name can vary by prompt, e.g. `Category` — and `Reasoning` string array when enabled). `#result.ToolCalls` (JArray of `{ToolName, CallId, Arguments, Result, Error}`). `#result.Metadata` (token counts, Frends Credit usage). Parse with `JObject.Parse(#result[AI Connector].Response)` before branching.

## Recipes in the guides

Semi-deterministic AI Processes (AI reasoning + Process control flow), reusable AI agents as Subprocesses, simple RAG as a standard Process, tokenizing/masking data before sending to AI, on-prem Ollama and Azure AI Inference setup, fine-tuned models.
