# Finding and Using Existing Tasks

Built for Frends 6.3.x from: `https://docs.frends.com/llms.txt` (## Tasks section), `/reference/shapes/activity-shapes/task.md`, `/tasks/task-guides/creating-custom-tasks`, `/management-and-operations/task-management` and `/docs/frends-6.2.0/frends-development/integrations/connectors` (search excerpts).

## Where Task documentation lives

1. **`https://docs.frends.com/tasks/`** — one page per system and one per method: `/tasks/tasks/<system>/<method>.md`, e.g. `/tasks/tasks/http/request.md`, `/tasks/tasks/sftp/uploadfiles.md`, `/tasks/tasks/microsoft-sql-server/executequery.md`. llms.txt lists every system and method under "## Tasks".
2. **`https://tasks.frends.com`** — the Task Portal. Get Task information from docs.frends.com/tasks, not from the portal.
3. **Source**: `https://github.com/FrendsPlatform/Frends.<Package>` (e.g. `Frends.File`). The Task page states all official Tasks are open source; the source is the ground truth for parameter classes and behaviour. `CommunityHiQ` repos are legacy community Tasks.

## Choosing

- The Task page: check the Tasks documentation for an existing Task first; otherwise request one, write a Custom Task, or use a Code Task (limited to the available namespaces).
- Custom Tasks from external sources run unknown code on the Agent — review the source before importing (Task page).
- **[opinion]** Practitioners often prefer protocol Tasks (HTTP, SQL, SFTP, AMQP) over system-specific wrappers unless the target system carries real domain complexity.

## Versions

- Task Management imports a chosen package version. Updating a package can update the Processes that use it or skip them; a Process can keep using an old Task version **with a warning**. Deployed Processes are not changed: a Task update only creates a new Process version.
- Packages targeting .NET Framework 4.7.1 / .NET Standard 2.0 are legacy and not available for Processes on newer targets (Task Management page).
- When reviewing an export, `LinkedTasks` / `UsedTasksJson` show exactly which packages a Process depends on.
