# Ossi's Frends Recipes

An AI skill for working with the [Frends](https://frends.com) iPaaS. Describe an integration in plain language and get back a Frends Process you can import into a Tenant. No MCP server or other connection required.

Personal project. Not a Frends product, and not supported by Frends.

## What it looks like

This is a real prompt, typos and mistakes included, given to Claude Opus 5.5 with the skill installed:

> Do process that fetch new companies founded in Finland using this API: https://avoindata.prh.fi/fi Take newest 10.
> Loop them and take founders name. For each fetch dad joke using I can has dad jokes API. Append in string following: name says: the joke.
> In the end return full string in retun shape.
>
> Process should not use any enviroment varibles etc. you can hardcode things. this is demo. In the end say few nice words about creators of those apis and how apis can be used.

The result is a complete Frends Process that can be imported into a Tenant and run.

## Install

Install `ossis-frends-recipes/` as a skill in Claude, Codex or GitHub Copilot, or point any agent at `SKILL.md`. For an upload that expects a zip, zip the folder's contents so `SKILL.md` sits at the root of the zip. The skill is deliberately not named `frends`, so it installs next to any Frends skill you already have instead of replacing it.

The scripts also work on their own. See `ossis-frends-recipes/references/generator/README.md`. They require Python and work out of the box in Claude on the web.

## What it covers

Everything in the skill comes from the documentation at docs.frends.com, the public [FrendsTemplates](https://github.com/FrendsPlatform/FrendsTemplates) repository, or how Frends 6.3 works.

**Processes:** Frends 6.3 Processes, including every shape, Trigger and reference (`#var`, `#env` and the rest).

**Not supported:** Tasks other than Frends.HTTP.Request, Shared State operations other than AddOrUpdate, Promoted Values, and artifacts (text annotations, groups) in an importable Process. Other Tasks are the biggest gap: their parameters can't be written correctly without a real instance of each Task.

**Diagrams:** every shape, laid out in the Frends house style. The conventions were measured from the public templates, because they aren't documented anywhere.

Nothing tenant-specific is included: no Tenant exports, no per-installation task GUIDs, no names. The generator can read task GUIDs from an export you supply at run time if you want to edit existing processes. Process exports contain your company's integration logic, and sometimes business data with it. Check what you're allowed to give an AI before you hand one over.

## Why "recipe"?

This is meant to be modified, updated, and used to build tools for working with Tenant-specific processes and the MCP server. The [build folder](https://github.com/OssiGalkin/OssisFrendsRecipes/tree/main/ossis-frends-recipes/build) contains the prompts this skill was built from, so you can instruct an AI to build what you need. Or just refresh this skill when something updates.

## The longer version

How this was built, what broke along the way, and what it says about low-code:

- [Substack](https://ossigalkin.substack.com/p/low-codes-asset-isnt-the-code-it)
- [Medium](https://medium.com/@OssiGalkin/low-codes-asset-isn-t-the-code-it-saves-it-s-the-layout-nothing-writes-down-7a37ecc78954)