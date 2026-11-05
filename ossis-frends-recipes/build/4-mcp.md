# Build 4 — the Frends MCP server (`references/mcp.md`, the MCP block in `SKILL.md`)

Fourth of four build prompts. Read `README.md` in this folder first: it says
which files this build owns, which it must leave alone, and what is pinned.

---

I want this skill to be useful to an AI assistant that has Frends MCP — the
MCP server *into* the platform — connected, and still useful to one that does
not. Keep it apart from Enterprise MCP (Processes exposed as tools through the
MCP Trigger), which is build 1's platform mechanics. Write down what the
skill knows about the server in advance — its guides, its tools, the rules it
imposes — and say for every piece of it where it came from, so a reader can
tell a documented fact from something the server served at one version.

The server's guides are live and always newer than this skill. So this build
does not compete with them. It writes a **map**: what the server is for, which
guide answers which task, which file in this skill holds the reasoning that the
guide does not, and what to do when there is no server to ask.

## 0. Inputs

- **Required:** the skill folder as it stands. Read `SKILL.md` and every file in
  `references/`, including `process-generation.md` from build 3. The platform
  semantics are there; do not re-derive them, and do not repeat them in
  `references/mcp.md` — point at them.
- **Public, first:** docs.frends.com. Map the site with `llms.txt` or
  `sitemap.md` and read every page about the Frends MCP server, connecting AI
  assistants to Frends, and enabling or authenticating that connection. Also
  check the Platform API reference for an MCP endpoint. Whatever the docs state
  about the server is **Documented** and outranks everything else below.
- **Public, second:** any public repository published by Frends for AI
  assistants that use the server. At the time of writing that means
  `github.com/Frends-Product-Management/frends-claude-plugin`, which is
  reported to list the tool names the server serves and to route tasks to its
  guides. Confirm the repository exists and what it actually contains before
  using it; record the commit you read. It is **Documented** for what it states.
  Do not copy its skills or workflows into this one: say in one line that it
  exists and what it is for, so a reader who has it installed knows which
  machinery runs the operational loop.
- **Expected:** a Frends MCP connection to any tenant — a sandbox is best. This
  is the only way to see the guides as served. Everything recorded from it is
  **Served by MCP**, with the server or Frends version it reported.
- **Not an input:** anything the tenant holds. See "Read only, record nothing
  tenant-specific". Also not `references/local-notes.md`, even if it is
  installed.

If there is no connection, build from the public sources alone. Mark the top of
`references/mcp.md` "not checked against a live server", leave out anything
only a server could supply, and say so in the report. Do not block, and do not
fill the gap from memory or from an earlier version of the file.

## 1. Read only, record nothing tenant-specific

Use only the server's discovery calls and its guides: the calls that list the
guides, describe the tools, and return a guide's text. At the time of writing
these are named like `list_guides`, `get_overview` and `get_guide`; if the
names differ, use whatever lists guides and tools.

- Do **not** call anything that creates, changes, validates against, deploys,
  activates, starts, imports or deletes. Not even a draft. This build documents
  the server; it does not exercise it.
- Do not list Processes, instances, Environment Variables, Agent Groups or
  Tasks beyond what is needed to confirm that a tool exists, and record none of
  what comes back.
- Never write down the tenant URL, the MCP endpoint address, a token, a Process
  or variable name, an Agent Group name, a person's name or an email address.
  Use `yourtenant` and `example.com`.

## 2. What goes into `references/mcp.md`

Open the file with its sources: the docs pages, the repository and commit, and
the server or Frends version the connection reported. Then, in this order:

1. **What the server is, and how to tell it is connected.** What it lets an
   assistant do, how it is enabled and authenticated (Documented only), and the
   check an assistant makes on itself: are the server's tools in its own tool
   list right now? Include, from the docs: the Frends version it arrived in, how
   access tokens get their scopes, and that the tools a client sees follow its
   scopes — a missing tool may be a missing scope, and a visible tool is not
   permission to use it. Include any per-Environment platform setting that makes
   deploy or run actions wait for a human's acceptance, and say that it adds to
   the assistant's own confirmation rather than replacing it.
2. **The two modes.** Write both, plainly:
   - **Connected.** The served guides are authoritative and newer than this
     file. Before any action on the live platform, fetch the guide that
     matches the task and follow it. Discover tools from the server, not from
     this file. Where a guide and this file disagree, the guide wins, and the
     assistant tells the user about the disagreement. The rest of the skill is
     still the reasoning layer — the `#result` limits, Handlebars rules,
     trigger evaluation and the review checklist apply to anything built
     through the server.
   - **Not connected.** Use this file as a map of what the server would do: to
     plan, to explain, to review. Never claim to have called it, never invent
     its output, and never present a tool name from this file as something
     callable. Route the user instead to the Control Panel steps in the other
     references, or to the generator in `process-generation.md` when the job is
     inside its scope.
3. **Task → guide → reasoning.** One table: the user's task, the guide that
   handles it as served at the recorded version, and the reference file in this
   skill that holds the judgment the guide does not. Every guide the server
   served appears in it exactly once.
4. **The guides.** One short paragraph each: what it is for, when to fetch it,
   and the rules it imposes. Gist only. If a paragraph starts to describe the
   steps of the guide, stop — that is the guide's job, and a copy goes stale
   the day the server changes.
5. **The tools.** By capability (discovery, environment variables, tasks,
   drafts and lifecycle, monitoring, process building, wiring), with the names
   as served at the recorded version and the line "names change between
   versions — discover them from the server". No parameter schemas.
6. **Conventions that matter without a connection.** The building conventions
   a guide states that an assistant should follow even when it is only
   *planning* a Process — naming of shapes, field modes, Handlebars versus C#
   mode, which code shape to prefer, what deployment does and does not
   activate, the default target. Each one attributed to the guide that states
   it. Where one restates something build 1 already sourced from the docs,
   point at the docs version instead of repeating it. Include the **pitfalls**
   the guides warn about in one line each — identifier mix-ups (for example
   different ids for an Environment and an Agent Group, or internal names that
   differ from display names), edits that replace a whole configuration, inputs
   that a run does not default, endpoints that are closed until a policy exists.
   These are the lines an assistant without a connection most needs.
7. **Safety.** Three tiers, by who decides:
   - **Read** — discovery, inspection, monitoring. Safe.
   - **Draft** — changes up to validation, never live. Safe and reversible.
   - **Commit** — promote, deploy, activate, start or run, import a Task,
     create or change an Environment Variable. Never on the assistant's own
     initiative: only after the user has asked for that specific action in
     this conversation, in the form the served guide requires (if a guide
     specifies an explicit confirmation block or reply, record it exactly), and
     through the platform's own confirmation setting if it is on.

   Plus the rules a guide states about secrets (never pass one as a literal) and
   about authentication on HTTP, API and MCP triggers (never invent it; it is
   configured through API Policies — point at `api-management.md`). Mark
   which rules a guide states (**Served by MCP**) and which are this skill's own
   (**Opinion**). The tier framing is opinion unless a guide states it.
8. **Server, generator, or editor.** When the assistant is connected to the
   tenant the Process is for, the server's building tools are the route. When
   it is not connected, or must hand over a file, or the target is another
   tenant, the generator is the route within its documented scope. Outside both,
   describe the shape-level change for the Process Editor. Drawing or lifting an
   existing export stays with the generator in every mode. Take the generator's
   scope from `process-generation.md`; do not restate it.
9. **What the server could not tell you.** Anything a guide leaves open that
   the skill's other files do not cover either. Short.

## 3. The MCP block in `SKILL.md`

At most ten lines, plus one router row pointing at `references/mcp.md`. It
carries the connected/not-connected rule in two sentences, the commit-tier rule
in one, and the pointer. Nothing about individual guides or tools: those live
in the reference file, where they can change without touching the router.

## 4. Size is the test

`references/mcp.md` should come out at about 150 lines. If it will not fit,
it is restating the guides: cut the restatement, not the map. The same test
applies to this prompt — if a thing the skill should know about the server
cannot be described in these sections, it does not belong in this skill. It
belongs in the guides, or in an architecture skill.

## 5. Conflicts

- **Guide versus docs:** say so in the file, name both, and do not pick one
  silently.
- **Guide or docs versus another reference file in this skill:** do not edit
  that file. Report it, so build 1 (or 3) can be re-run.
- **Public repository versus served guides:** the served guides win; note the
  repository's commit and the server version so the gap can be dated.

## 6. Done means

Run the scenarios in `scenarios.md` marked for build 4, **twice**: once as the
skill's user with a connection and once without. With only `SKILL.md` and
`references/` open. Report pass/fail for each scenario and mode. A failure is
fixed in `references/mcp.md` or the MCP block, never in the scenario.

Then run the privacy grep from `README.md` and diff the skill folder: nothing
outside `references/mcp.md`, the MCP block and its router row may have changed.

Close with a report: the server or Frends version seen; the guides and tool
categories, and what changed since the previous `references/mcp.md`; every
disagreement found; and anything you could only have learned by calling a
non-discovery tool, which you therefore did not learn.
