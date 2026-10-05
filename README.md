# OssisFrendsRecipes

An AI skill for the [Frends](https://frends.com) iPaaS, with tooling that generates importable Frends Processes and Frends-style BPMN diagrams from a spec.

Personal project. Not a Frends product, not supported by Frends.

```
ossis-frends-recipes/
  SKILL.md                 the skill: vocabulary, reference values, error handling, review checklist
  references/              deeper topics, loaded on demand
  scripts/                 frendsgen: spec -> process.json, spec -> .bpmn, export -> picture
  build/                   the three prompts that reproduce all of the above, and how they fit together
```

Install `ossis-frends-recipes/` as a skill in Claude (or point any agent at `SKILL.md`). The skill is deliberately not named `frends`, so it installs next to any Frends skill you already have instead of replacing it. The scripts also work on their own: see `ossis-frends-recipes/scripts/README.md`.

## What is in here, and what is deliberately not

Everything in the skill was verified against the live documentation at docs.frends.com, or observed directly — counted over the public [FrendsTemplates](https://github.com/FrendsPlatform/FrendsTemplates) repository, or seen when generated files were imported into a Tenant and run there — and says which. There are no claims carried over from memory or older notes: nothing on certifications, retention limits or runtime internals that the docs do not state. For those, the skill tells the model to fetch the docs or say it does not know.

Nothing tenant-specific is included: no Tenant exports, no per-installation task GUIDs, no names. The generator reads task GUIDs from an export you supply at run time.

## Snapshot and recipe

The skill is a snapshot and will go stale; Frends ships a minor version roughly every quarter. The prompts that produced it are inside the skill folder, so a copy of the skill is also a copy of the means to refresh it. Start at `ossis-frends-recipes/build/README.md`.
