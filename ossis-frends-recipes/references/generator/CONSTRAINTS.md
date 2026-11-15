# Connection and containment constraints from docs.frends.com

Measurement gives geometry. These give meaning and the rules geometry cannot show.
Quoted from docs.frends.com. Request the `.md` form of a page to re-fetch it;
plain page URLs may already return `text/markdown`, but `.md` is what the docs
advertise and what a plain HTTP client should ask for.

## Task — /reference/shapes/activity-shapes/task
> "Tasks are always one sequence flow in, one out, with optionally an Intermediate
> Return or Catch shape connected to them in addition."

## Scope — /reference/shapes/scope-shapes/scope
> "Scopes are always one sequence flow in, one out, with optionally a Catch shape
> connected to them in addition."
> "the execution inside a Scope starts with a Trigger or Start shape, and ends to a
> Return or Throw shape"
> "There can be only and exactly one Trigger shape within the Scope. There can
> however be as many Return or Throw shapes within the Scope as needed, as well as
> Scopes within other Scopes."
> "Unlike Processes or Subprocesses, the Trigger shape within a Scope does not have
> any parameters assigned to it."

Corpus agrees: every subProcess contains exactly one Type-13 startEvent whose name is
empty and whose SelectedTypeId is the empty string. 61 containers, 61 Type-13 starts.

## Exclusive Decision — /reference/shapes/decision-shapes/exclusive-decision
> "You also have to connect the shape to exactly two further branches in the Process."
> "C# expression field ... must evaluate into a boolean (true or false) value."
> "Default branch will be executed, if the condition results in a false value."

Corpus agrees at 99.3% (in=1 out=2). The 0.7% that differ are joins — a gateway with
2 or 3 incoming flows and still 2 outgoing. So "exactly two outgoing" is a hard rule;
"exactly one incoming" is not.

## Inclusive Decision — /reference/shapes/decision-shapes/inclusive-decision
> "Each branch of the Inclusive Decision must be given a unique name"
Every branch carries a condition; zero, one or several may run. Corpus has exactly one
inclusive gateway, with 3 named branches (create / update / delete).

## Catch — /reference/shapes/event-shapes/catch
> "Allowed shapes to catch from are Scope and Task shapes."
> "The error handling must be done within one shape after the Catch shape."
> "The error handling path must also join back to the main Process flow right after
> the shape you are catching errors from. There can be no shapes in between."
> "the shape performing error handling cannot have a second Catch shape directly
> connected to it"
> "Same error handling shape also cannot be used to handle multiple catched errors"

Catch does NOT end the flow path — it is the one event shape with an outgoing flow.

Catch is not a `boundaryEvent`. It is an `intermediateCatchEvent` +
`signalEventDefinition`, Type 14, reached from the guarded shape by an ordinary
sequence flow. The guarded shape (Task, Scope or Call Subprocess) has two outgoing
flows; the Catch's one successor rejoins at the other. A Foreach cannot have a Catch.

## Throw vs Intermediate Return — /reference/.../intermediate-return
> "Unlike Return shape, Intermediate Return shape does not end the Process execution
> and is also always presented as an alternative execution path in the Process."
> "You can only connect Intermediate Return shape to a Task shape, Call Subprocess
> shape, Assign Variable shape or Code Task shape."

They are different elements. Throw is `intermediateThrowEvent` +
`signalEventDefinition` (Type 6); Intermediate Return is `endEvent` +
`signalEventDefinition` (Type 17), reached by a second outgoing flow from its activity.

## Shapes not present in the public corpus
Catch, plain Scope, Call Subprocess, DMN Task, AI Connector, Checkpoint, Scheduled
Resume, Signal Resume. Their elements are in the Type table in
references/process-generation.md. The extractor reports any unknown Type loudly.
