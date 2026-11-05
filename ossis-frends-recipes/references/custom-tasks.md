# Creating Custom Tasks (C# / .NET 8)

**Built for Frends 6.3.x** from `/tasks/task-guides/creating-custom-tasks` (full read), `/tasks/task-guides/frends-official-task-development-guidelines` and `/management-and-operations/task-management` (search excerpts).

- The custom-task page calls it the **".NET 8 Task template"** and links the monorepo folder `github.com/FrendsPlatform/FrendsTasks/tree/main/FrendsTaskTemplate`; minimum .NET SDK 8.0. The official guidelines page still links the old `FrendsPlatform/FrendsTaskTemplate` repo and says the template targets .NET 8 — the two pages disagree on the location; the custom-task page is the newer link.
- `FrendsTaskMetadata.json`: the custom-task page says at the **root of the NuGet package**; the guidelines say it **must exist in the Task project folder** (handled by the template). Format: `{"Tasks":[{"TaskMethod":"Namespace.Class.Method"}]}`.
- Processes in 6.3 compile to .NET 10 (6.3.0 release notes); no page read says the Task template moved past .NET 8. The Task Management page still describes `.NETCoreApp 6.0` packages as working for Processes targeting ".NET versions 6 and 8, which is the latest and default" — dated wording.
- The guidelines say **target .NET 8 in all new Task development** (.NET 6 only with approval), while the same page's sample project file still shows `<TargetFrameworks>net6.0</TargetFrameworks>`. The template's own project files (`FrendsTasks` repo, main-branch archive read at build time) target **`net8.0`**, so the template follows the guidelines, not the sample.
- **Companion:** `FrendsTaskSkills/frends-task-creator` in the same repository is an Agent Skill (Claude Code plugin `frends-task-creator@frends-tasks`) that scaffolds from `dotnet new frends-task`, swaps the reserved `Frends.*` prefix for your own, and checks the guidelines. This file does not depend on it.
- Partner Tasks must not use the `Frends.*` namespace (guidelines). Task parameters and results must not expose third-party classes (guidelines).
- Carried, not re-verified this run (template README not read): the `dotnet new` scaffold commands and the Input/Options/Result + CancellationToken skeleton below.

Primary doc: `https://docs.frends.com/tasks/task-guides/creating-custom-tasks.md` (also `frends-official-task-development-guidelines.md` and `publishing-tasks-to-frends-official-channels.md` in the same folder).

A Custom Task is a .NET class library packed as a NuGet package (.nupkg) and imported via the Tasks admin page in the Control Panel. Use one when no ready-made Task fits and the logic needs third-party libraries that Code Tasks can't load.

## Template (current, .NET 8)

Template location per the custom-task page: `https://github.com/FrendsPlatform/FrendsTasks/tree/main/FrendsTaskTemplate`.

Install and scaffold (commands from the template README, still valid):

```
dotnet new install frendstasktemplate --nuget-source https://pkgs.dev.azure.com/frends-platform/frends-tasks/_packaging/main/nuget/v3/index.json
dotnet new frends-task -F Frends.ClassName.MethodName -D "Description of the Task"
dotnet new frends-task -h        # help
dotnet new update                # update template
```

Naming convention: `Company.System.Action`, e.g. `Frends.Xml.Write`. Requires .NET SDK 8.0+. Optional: `FrendsTaskAnalyzers` NuGet enforces official-Task conventions.

## Task method rules

- Task = **public static method with a return value**. Non-static or void methods are not discovered. **No overloads** of the same method name.
- Method parameters become the Task's UI parameters. Class-typed parameters render as structured groups; keep hierarchy ≤ 2 levels.
- New-generation convention: an `Input` class, a `Connection`/`Options` class, a `Result` class, `CancellationToken` as last parameter, one Task method per package (`Frends.System.Action` package with `Action` method).

Modern-style skeleton:

```csharp
namespace Frends.MySystem.DoSomething;

public class DoSomething
{
    /// <summary>Does the thing.</summary>
    /// <returns>Object { string Body, int StatusCode, bool Success }</returns>
    public static async Task<Result> Execute(
        [PropertyTab] Input input,
        [PropertyTab] Options options,
        CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        // ... implementation
        return new Result { Success = true };
    }
}
```

`Input` holds required fields, `Options` optional/advanced ones, both documented with XML comments and the attributes below; return a strongly typed `Result` class, not `object`. Async `Task<T>` return values are supported.

## Parameter attributes (System.ComponentModel / DataAnnotations)

- `[DefaultValue("...")]` — shown in editor. Values are **expressions**: `"true"` for bool, `"\"C:\\Temp\\\""` for a string.
- `[PasswordPropertyText]` — value logged as `<< Secret >>`. Mandatory for secrets.
- `[UIHint(nameof(Other), "", condition1, condition2)]` — show field only when `Other` has one of the listed values (bool or enum members).
- `[DisplayFormat(DataFormatString = "Json"|"Text"|"Xml"|"Sql"|"Expression")]` — default editor type of the field.
- `[PropertyTab]` — group method parameters as tabs: `public static bool Delete([PropertyTab] string fileName, [PropertyTab] Options options)`.

## Discovery, docs, packaging

- `FrendsTaskMetadata.json` (location: see the disagreement above) whitelists Task methods: `{"Tasks":[{"TaskMethod":"Frends.TaskLibrary.FileActions.DoFileAction"}]}`.
- **XML documentation comments** surface in the Process Editor. Enable XML doc file generation; the file must be inside the NuGet and named after the package id (`Frends.TaskLibrary.xml`). Parameter-level comments are checked first, then type-level.
- Package with `dotnet pack`. **Assembly name and package id must be identical** (`Frends.TaskTemplate.dll` ↔ `Frends.TaskTemplate.1.0.0.0.nupkg`). Legacy code sometimes needs nuget.exe + .nuspec.
- Import: Task Management → **Import Task NuGet**. Updating a package can skip updating Processes that use it; deployed Processes are never changed in place — an update only creates a new Process version (Task Management page).

## Debugging official Tasks

Sources: `git clone https://github.com/FrendsPlatform/Frends.<Package>.git` → open the .sln → run unit tests first (some need a target system; check README) → replicate the issue as a unit test. Fix routes: (1) GitHub issue + contact Frends support, (2) fork + PR + email support, (3) copy source into your own Custom Task.

## Legacy template — maintenance only

`https://github.com/CommunityHiQ/TaskTemplate` (`dotnet new frendstask --name Frends.Community.X --className X --taskName Y --EnableCommunityTask true`) targets the older community-task style (`Frends.Community.*` prefix, MIT license). Treat it as **maintenance-only for existing community Tasks**; all new development should use the official .NET 8 template above. CommunityHiQ also hosts many older community Task repos.
