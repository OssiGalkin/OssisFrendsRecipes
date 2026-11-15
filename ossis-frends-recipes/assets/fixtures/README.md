# Shape reference export, Frends 6.3.2

One ProcessExport made by hand in the Frends 6.3.2 Process Editor
(`FrendsVersion` 6.3.2.5628, `ProcessExecutionVersion` 6.3.6, `net10.0`):
`shapes-6.3.json`. It places every shape type, eleven Triggers, artifacts, a
coloured shape and the `#trigger`/`#process` reference list.

Scrubbed before committing: Tenant GUIDs (Process, Subprocess, Task, AI model)
are replaced by `00000000-0000-4000-8000-...` placeholders, one per original
GUID; names, the author, routes and dates are neutral. Nothing else was
changed, so the file is still Frends' own output and the validator must report
nothing on it.

It is the answer key for every construct beyond the public templates. Make a
new one the same way when the Frends version moves.

## Not in the export

These are written the way the Frends 6.3.2 editor writes them:

- **Catch on a Call Subprocess.** The same as a Catch on a Task or a Scope (both
  are in the export). The Call Subprocess (Type 7, `callActivity`) has two
  outgoing flows: one to the next step, one to the Catch (Type 14,
  `intermediateCatchEvent` + `signalEventDefinition`, parameter `expression`
  naming the error variable, e.g. `error`). The Catch flows to exactly one
  handler shape, which rejoins the main path.
- **Subprocess to call on unhandled error.** Not drawn in the BPMN. It is one
  `ElementParameters` entry: Type 18, `Id` `globalErrorHandler`, `Name`
  `GlobalErrorHandler`, `SelectedTypeId` the Subprocess GUID, and `Parameters`
  the Subprocess's parameters in `{"mode", "value"}` form. The Subprocess is
  listed in `UsedSubprocessesJson` (`__localCall`) and `LinkedSubProcess` like
  a called one. When no Call Subprocess shape in the Process uses that
  Subprocess, the handler entry alone is what puts it in those two lists.
- **Scheduled Resume loop.** Checkpoint (Type 24, `intermediateCatchEvent` +
  `messageEventDefinition`; `correlationId`, `ttlMinutes`,
  `continueExecution`) -> Exclusive Decision -> the default ("no") branch to
  Scheduled Resume (Type 25, `intermediateCatchEvent` +
  `timerEventDefinition`; integer `maxIterations` and
  `rehydrationIntervalMinutes`) -> back into the Checkpoint, which therefore
  has two incoming flows. The other branch continues the Process.
- **Service Bus Trigger.** `$type` `ServiceBusTrigger`, config keys in this
  order: `queueName`, `connectionString`, `maxConcurrentMessages`,
  `messagePrefetchCount`, `consumeMessageImmediately`, `reply`, `replyErrors`,
  `replyTo`, `retryMessageProcessingIfExceptionThrown`. With the eleven in the
  export, that makes all twelve Triggers.
