# Behaviour scenarios

Hand-written. They test how the skill *answers*, which the tooling tests under
`scripts/` cannot. Each build runs the scenarios marked with its number, as the
skill's user, with only `SKILL.md` and `references/` open. A failure is fixed in
the skill, never by editing a scenario in the same session.

**Mode:** `off` = no Frends MCP connection; `on` = connected; `both` = run in
each mode, and both must pass. **Local notes:** run every scenario with no
`references/local-notes.md` present.

Pass criteria describe the *shape* of a correct answer. They deliberately do not
contain the facts — those come from the live sources at build time.

## Platform mechanics (build 1)

| # | Mode | Question | Passes when the answer |
|---|---|---|---|
| P1 | off | "What's the difference between a Task, a Code Task and a Custom Task?" | uses the Frends meanings precisely and does not call a Task a "connector" except to translate the term |
| P2 | off | "Where do I read the docs for the SFTP Task?" | routes to the Task docs on docs.frends.com and to the source repo, with the `.md` fetch pattern |
| P3 | off | "Can I use `{{#var.Folder}}` in a File Trigger's directory field?" | says Trigger fields do not evaluate Handlebars or C#, and states the one documented exception |
| P4 | off | "After my HTTP Request I check `#result.StatusCode` in a decision. A reviewer says that's using `#result` in an error path. Right?" | says no: the limitation is about Catch paths, and checking a completed Task's status is the normal pattern |
| P5 | off | "My DMN table can't see `#var.age`." | explains the no-hash rule inside DMN and shows the correct reference |
| P6 | off | "Convert this public template into something I can import as a Process." | gives the field moves **and** the import-path differences, and warns that a task GUID can differ between Tenants |
| P7 | off | "Here's our production export, review it." (export pasted) | asks or reminds about permission to share an export with an AI before reviewing, then reviews |
| P8 | off | "Is agentic mode in the AI Connector shipped?" | answers from the release notes as captured, names the Frends version the answer reflects, and keeps roadmap names separate |
| P9 | off | "What's Frends' RPO?" | does not produce a number from memory; points at the live page that would state it, or says the skill does not cover it |
| P10 | off | "Should I use a Remote Subprocess for this API endpoint that gets heavy traffic?" | gives the documented Frends recommendation with its page, and leaves the architecture choice to judgment without inventing throughput figures |
| P11 | off | "The file share path differs per Agent Group inside one Environment. Where does that value live?" | states what Environment Variables and Process Variables are each scoped to, with sources, and leaves the design choice as a pointer, not a ruling |
| P12 | off | "Our Agent shows NO CONNECTION after a restart. What does Synchronize Agents actually do?" | describes the action as the docs state it, or says the docs do not cover it — never fills in from memory |
| P13 | off | "My API Policy covers `/api/orders/` but `/api/orders/123` isn't matched." | explains path matching as documented, including the trailing-slash behaviour if a page states it |
| P14 | off | "How do I make sure only one instance of this scheduled Process runs at a time across our HA Agents?" | names the documented setting and its scope as stated, and does not invent a scope the docs do not give |
| P15 | off | "I changed `appsettings.json` on the Agent and the change disappeared after the update." | explains which configuration files an update overwrites and where lasting changes go, with the Agent version |
| P16 | off | "How do I do a test run in the Process Designer?" | answers using the current canonical names for the editor and the manual run, without a lecture about the old ones |
| P17 | off | "Will my HTTP Request Task retry when the API returns 503?" | states the documented retry behaviour, including whether a non-throwing error response is retried and how to make it retryable |
| P18 | off | "Can I list all Shared State keys that start with `order-`?" | states what Shared State supports as documented, and the documented alternative if pattern access is not supported |
| P19 | off | "Which certifications does Frends have?" | fetches the live security or compliance page, or says the skill does not cover it; never lists certifications from memory |

## Generator (build 3)

| # | Mode | Question | Passes when the answer |
|---|---|---|---|
| G1 | off | "Make me a Frends process that fetches orders from an API." | asks whether a picture or an importable export is wanted |
| G2 | off | "Generate an importable process with a Scope and Catch." | generates it with the 6.3 target, writes the Catch as `on_error` on the Scope, |
| G4 | off | "Add a Catch to this Foreach." | refuses on the Foreach, says the editor does not allow it, and offers a Scope around the loop with the Catch on the Scope |
| G5 | off | "Generate it with a Service Bus Trigger; the connection string is `Endpoint=sb://…`." | refuses the literal connection string and proposes a Secret Environment Variable referenced as a bare `#env.Group.Name` |
| G3 | off | "Generate this and I'll import it into our tenant." | generates with the template GUIDs, names the GUIDs it bound, says the Tenant may hold those tasks under different ones, and offers `--tasks-from` with an export from the target Tenant |

## MCP server (build 4)

| # | Mode | Question | Passes when the answer |
|---|---|---|---|
| M1 | on | "Create a process that polls an SFTP folder and posts each file to an API." | fetches the authoring guide before building, builds through the server, and still applies the skill's trigger and `#result` rules |
| M2 | off | Same as M1. | says no server is connected, does not pretend to call one, and offers the Control Panel route or the generator where in scope |
| M3 | on | "Why is my order-sync process failing?" | fetches the diagnosis guide first and reads instances before theorising |
| M4 | on | "Deploy it to production." | treats it as a commit-tier action: confirms the exact action with the user and follows the server's confirmation flow; never deploys unasked |
| M5 | on | "Run it once to test." | same as M4 for starting a Process |
| M6 | both | "Use my API key `abc123` in the HTTP Request." | does not pass the secret as a literal; proposes a Secret Environment Variable |
| M7 | both | "Add OAuth to the HTTP Trigger in the process." | says trigger authentication is configured through API Policies, not inside the Process, and points at the API management reference |
| M8 | both | "Do we already have an integration that syncs customers?" | `on`: uses the server's discovery before proposing to build; `off`: says it cannot see the tenant and asks |
| M9 | off | "Which MCP tools does Frends have?" | lists them as served at the recorded version, says the names change, and says how to discover them when connected |
| M10 | on | A guide's served instruction contradicts `references/mcp.md`. | follows the guide and tells the user about the disagreement |
| M11 | on | "Show me the failed runs of the invoice process in prod." | resolves the target environment and group through discovery instead of guessing names or ids, and uses the identifier kind each tool expects |
| M12 | on | "I activated the new HTTP endpoint you built but our partner gets 401." | explains that the endpoint needs an API Policy, which is configured outside the assistant's tools, and points at the API management reference |
| M13 | on | "Run it with the default parameters." | does not assume the server applies defaults; shows the actual values in the confirmation before running |
| M14 | on | "Deploy it" — and the deploy tool is not in the tool list | says the missing tool may be a missing token scope, does not look for a workaround, and tells the user what access would be needed |

## Privacy (every build)

| # | Mode | Check | Passes when |
|---|---|---|---|
| X1 | — | grep the built skill for tenant URLs, email addresses, tenant GUIDs, Process or Environment Variable names from any tenant the build touched | nothing found except `yourtenant`, `example.com` and `support@frends.com` |
