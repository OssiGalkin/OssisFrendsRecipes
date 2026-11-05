# How this skill is reproduced

This skill is a snapshot. These are the recipes. There are four, because the
four parts have different inputs, different cadences and different proof:

| # | Prompt | Builds | From | Proof it worked |
|---|---|---|---|---|
| 1 | `1-skill.md` | `SKILL.md`, `references/` | live docs.frends.com | every claim has a live source |
| 2 | `2-diagram.md` | the diagram package, `scripts/docs/` | a zip of real exports | corpus round-trip, and looking at PNGs |
| 3 | `3-export.md` | the export generator, `scripts/tests/`, `scripts/examples/`, `scripts/README.md`, `references/process-generation.md` | the same zip, parts 1 and 2, and a human with a tenant | three corpus loops, then a real import |
| 4 | `4-mcp.md` | `references/mcp.md`, the MCP router block in `SKILL.md` | public MCP documentation, and a Frends MCP connection to any tenant | the scenarios in `scenarios.md`, run with and without a connection |

Run them **in that order, each in its own session**, handing each session the
skill folder as it stands. 2 reads what 1 wrote about shapes. 3 reads what 1
wrote about platform semantics and drives 2's layout function. 4 reads what 1
wrote about platform semantics and what 3 wrote about the generator, because
it has to say when to use the MCP server and when to use the generator. Nothing
flows backwards except findings: if a later build discovers that the docs or
the MCP server disagree with `SKILL.md`, that is reported and fixed by
re-running the relevant part of 1, not patched in place by the later session.

Rebuild a part when **its** inputs change, not when another part's do:

- 1: a Frends minor version, or a claim in the skill found to be wrong.
- 2: a richer corpus, a working real renderer, exports that look different.
- 3: a richer corpus, exports from a target tenant, an import that starts
  failing. Also whenever 2's layout interface changes.
- 4: the MCP server serves different guides or tools, a Frends version moves
  the MCP server, or the public MCP documentation changes. Also whenever 3's
  scope changes, since 4 says when the generator is the right tool.

## Who owns which file

One owner per file. A build never rewrites a file it does not own; it may add the
marked section it owns inside another build's file.

| File | Owner |
|---|---|
| `SKILL.md` frontmatter (`name`, `description`) | **hand-written; pinned below, never output** |
| `SKILL.md` local-notes sentence | **hand-written; pinned below, never output** |
| `SKILL.md` body | 1 — except the generator router row and sentence (3) and the MCP block and router row (4) |
| `references/*.md` | 1 — except the files and sections below |
| `references/process-generation.md` | 3 |
| `references/templates-and-exports.md` | 1 — except "The two import paths validate differently" and the task-GUID paragraph, owned by 3 (docs cannot supply them; only imports can) |
| `references/mcp.md` | 4 |
| `scripts/frendsgen/diagram/`, `scripts/docs/` | 2 |
| everything else under `scripts/` | 3 |
| `build/*.md`, including `scenarios.md` | hand-written |
| `references/local-notes.md` | **written by whoever installs the skill; never built, never committed** (below) |

## Pinned inputs

These are decisions, not discoveries. A regeneration that changes them is wrong.

- **Name:** `ossis-frends-recipes`. Deliberately not `frends`, so the skill
  installs beside any other Frends skill instead of replacing it.
- **Description** (hand-authored; "Frends" alone must trigger it, the rest is
  disambiguation):

  > Expert knowledge for the Frends iPaaS (Integration Platform as a Service). Use this skill whenever the user mentions Frends, asks how to build, modify, or review integrations, Processes, Subprocesses, APIs, Tasks, or Triggers in Frends, needs help with C# expressions, Handlebars, or reference values (#var, #env, #result, #trigger, #process), wants to create custom Tasks in C#/.NET, asks about API Management, API Portal, Business Automation Portal (BAP), the AI Connector or agentic AI in Frends, debugging or troubleshooting a failing Process or Process Instance, monitoring and operating running Processes, Process/Template exports and imports, platform architecture (Agents, Agent Groups, HA, scalability, security), working through Frends MCP, or migration from BizTalk or other iPaaS platforms to Frends. Also use for reviewing exported process.json files and Frends Templates, and for generating importable Process exports or Frends-style BPMN diagrams from a spec.

- **Local-notes sentence** (copied verbatim into `SKILL.md`, directly after the
  "No unsourced claims" rule; no build may reword, move or drop it):

  > **Local notes.** If `references/local-notes.md` exists, whoever installed this skill added it, and no build has verified it. Read its header before using any line of it, prefer a live source, and say when an answer rests on it. Public installs do not have this file; its absence is normal.

- **One skill, not two.** Generation and MCP routing are the skill applied to
  narrower tasks and depend on format and platform knowledge the skill already
  holds. Split one out only when the router spends more than about a fifth of
  its lines on it.
- **Works with or without a connection.** Every part of the skill must give a
  useful answer when no Frends MCP server is connected, and must defer to the
  server's live guides when one is. A build that makes either mode depend on
  the other is wrong.
- **Nothing unsourced, nothing private.** No "believed true" content in any
  built file. No tenant exports, tenant GUIDs, tenant URLs, Process names,
  Environment Variable names, names or email addresses anywhere.

## Evidence classes

Every built claim carries one. Build 1 defines how they are marked; the others
use the same marks.

| Class | Meaning | Reproducible by |
|---|---|---|
| **Documented** | a live docs.frends.com page or a public Frends repo says it | anyone |
| **Public output** | counted over the public templates or other public exports | anyone |
| **Served by MCP** | returned by the Frends MCP server's own discovery calls and guides, at a named server or Frends version | anyone with a connection to any tenant |
| **Tenant observation** | an import result, or a tenant's own export | only someone with a tenant |
| **Opinion** | a working heuristic from practice | nobody; say so |

"Served by MCP" is not "Tenant observation": the guides and tool list are
product content, the same in every tenant on that version. What a tenant
*holds*, seen through the server, is tenant data and is never recorded.

## Local notes (optional, never committed)

`references/local-notes.md` is for what the person installing the skill knows
and the public sources do not: their own conventions, their Tenant's naming,
field notes. The skill must be fully useful without it, and a public install
never has it.

- **Not built and not committed.** List it in `.gitignore`.
- **Not a source for any build.** A build run with the file installed must
  produce the same files as one run without it.
- **Its header tells the reader how to use it.** At minimum: say when an
  answer relies on it; check a live source first; a live source that disagrees
  wins; never put an unverified line into a deliverable that leaves your hands.

## Behaviour scenarios

`scenarios.md` holds hand-written questions with pass criteria. They test how
the skill *answers*, which the tooling tests in `scripts/` cannot. Builds 1, 3 and
4 run the scenarios they own before declaring done, and report pass/fail per
scenario. A scenario that fails is fixed in the skill, never by editing the
scenario in the same session.

## Accepting a rebuild

**Build 1.** Every claim is marked with its evidence class (step 12 of
`1-skill.md`), every counted claim was recomputed rather than carried over, the
build reported what it could not source, the sections builds 3 and 4 own and
the pinned local-notes sentence are still there unchanged, and the build-1 scenarios
pass.

**Builds 2 and 3.** From `scripts/`, with the public corpus unzipped somewhere:

```
python3 -m tests.test_generator
python3 -m frendsgen selftest <corpus>
python3 -m frendsgen.diagram.extract <corpus> work/ && python3 -m frendsgen.diagram.roundtrip work/spec work/raw work/gen
python3 -m frendsgen generate examples/magento-zoho-orders.yaml -o /tmp/m.json && python3 -m frendsgen picture /tmp/m.json -o /tmp --check
grep -rIE "@[a-z]+\.(com|fi)|frendsapp\.com" . | grep -vE "example\.com|yourtenant"   # expect: support@frends.com only
```

Then look at the picture. Then, for build 3 only, one real import of a `--fresh`
file generated with `--tasks-from` — until that has happened, the README says
the current output has not been imported.

**Build 4.** `references/mcp.md` names the server or Frends version it was
taken from and the evidence class of every line; the MCP scenarios pass
twice, once with a connection and once without; the privacy grep above finds
nothing new; and nothing outside `references/mcp.md` and the MCP block in
`SKILL.md` changed (diff to confirm).
