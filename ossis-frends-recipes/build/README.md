# How this skill is reproduced

This skill is a snapshot. These are the recipes. There are three, because the
three parts have different inputs, different cadences and different proof:

| # | Prompt | Builds | From | Proof it worked |
|---|---|---|---|---|
| 1 | `1-skill.md` | `SKILL.md`, `references/` | live docs.frends.com | every claim has a live source |
| 2 | `2-diagram.md` | the diagram package, `scripts/docs/` | a zip of real exports | corpus round-trip, and looking at PNGs |
| 3 | `3-export.md` | the export generator, `scripts/tests/`, `scripts/examples/`, `scripts/README.md`, `references/process-generation.md` | the same zip, parts 1 and 2, and a human with a tenant | three corpus loops, then a real import |

Run them **in that order, each in its own session**, handing each session the
skill folder as it stands. 2 reads what 1 wrote about shapes. 3 reads what 1
wrote about platform semantics and drives 2's layout function. Nothing flows
backwards except findings: if 2 or 3 discovers that the docs disagree with
`SKILL.md`, that is reported and fixed by re-running the relevant part of 1,
not patched in place by the tooling session.

Rebuild a part when **its** inputs change, not when another part's do:

- 1: a Frends minor version, or a claim in the skill found to be wrong.
- 2: a richer corpus, a working real renderer, exports that look different.
- 3: a richer corpus, exports from a target tenant, a Frends MCP connector, an
  import that starts failing. Also whenever 2's layout interface changes.

Log a run in the commit message, not in a file:
`regen: export generator — <model>, prompts@<sha>, corpus FrendsTemplates@<sha>`.
Include no-change runs (`--allow-empty`); a run that changed nothing is evidence
too.

## Who owns which file

One owner per file. A build never rewrites a file it does not own; it may add the
marked section it owns inside another build's file.

| File | Owner |
|---|---|
| `SKILL.md` frontmatter (`name`, `description`) | **hand-written; input to build 1, never output** |
| `SKILL.md` body | 1 — except the router row and the one sentence pointing at `scripts/`, owned by 3 |
| `references/*.md` | 1 — except the two below |
| `references/process-generation.md` | 3 |
| `references/templates-and-exports.md` | 1 — except "The two import paths validate differently" and the per-installation GUID paragraph, owned by 3 (docs cannot supply them; only imports can) |
| `scripts/frendsgen/diagram/`, `scripts/docs/` | 2 |
| everything else under `scripts/` | 3 |
| `build/*.md` | hand-written |

## Pinned inputs

These are decisions, not discoveries. A regeneration that changes them is wrong.

- **Name:** `ossis-frends-recipes`. Deliberately not `frends`, so the skill
  installs beside any other Frends skill instead of replacing it.
- **Description** (hand-authored; "Frends" alone must trigger it, the rest is
  disambiguation):

  > Expert knowledge for the Frends iPaaS (Integration Platform as a Service). Use this skill whenever the user mentions Frends, asks how to build, modify, or review integrations, Processes, Subprocesses, APIs, Tasks, or Triggers in Frends, needs help with C# expressions, Handlebars, or reference values (#var, #env, #result, #trigger, #process), wants to create custom Tasks in C#/.NET 8, asks about API Management, API Portal, Business Automation Portal (BAP), the AI Connector or agentic AI in Frends, monitoring and operating running Processes, Process/Template exports and imports, platform architecture (Agents, Agent Groups, HA, scalability, security), or migration from BizTalk or other iPaaS platforms to Frends. Also use for reviewing exported process.json files and Frends Templates, and for generating importable Process exports or Frends-style BPMN diagrams from a spec.

- **One skill, not two.** Generation is the skill applied to a narrower task and
  depends on format knowledge the skill already holds. Split it out only when
  the router spends more than about a fifth of its lines on it.
- **Nothing unsourced, nothing private.** No "believed true" file. No tenant
  exports, tenant GUIDs, tenant URLs, names or email addresses anywhere.

## Accepting a rebuild

**Build 1.** Every claim is marked with its evidence class (step 11 of
`1-skill.md`), every counted claim was recomputed rather than carried over, the
build reported what it could not source, and the two sections build 3 owns in
`references/templates-and-exports.md` are still there.

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
