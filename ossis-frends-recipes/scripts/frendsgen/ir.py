"""Intermediate representation for a Frends Process.

The IR is a tree of *sequences*. A sequence is a list of Nodes executed
left to right. Containers (Foreach, While) and the yes/else branches of a
Decision hold nested sequences.

Deliberate limits (see README):
  * every Trigger is wired to the same first shape (as Frends requires)
  * no arbitrary merges: a branch either terminates or merges back to the
    step immediately after its decision
  * the only cycle is the bounded Checkpoint -> decision -> Scheduled Resume
    loop (WaitGate); no other back edges
  * a Catch is an attribute of the shape it guards: one handler shape, which
    rejoins at the guarded shape's successor (or terminates)

Every Node carries `bid` (its BPMN element id), allocated exactly once by
ids.allocate() before emission. Both the BPMN emitter and the
ElementParameters emitter read that same attribute off that same object.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict


class SpecError(Exception):
    """Raised when a spec asks for something the IR cannot express."""


# --- value cells -----------------------------------------------------------
# Every editor field serialises as {"mode": ..., "value": ...}.
# "list" is new in 6.3.2 (AI Connector allowedMcpTools).
VALID_MODES = {"text", "csharp", "select", "toggle", "integer", "json", "xml", "sql",
               "list"}


@dataclass
class Val:
    mode: str
    value: Any

    def __post_init__(self):
        if self.mode not in VALID_MODES:
            raise SpecError(f"unknown field mode {self.mode!r}")

    def json(self) -> Dict[str, Any]:
        return {"mode": self.mode, "value": self.value}


def V(mode: str, value: Any) -> Val:
    return Val(mode, value)


# --- nodes -----------------------------------------------------------------


@dataclass
class Node:
    name: Optional[str] = None
    description: Optional[str] = None
    should_not_log_result: Optional[bool] = None
    bid: Optional[str] = None        # BPMN element id, allocated once
    # geometry, filled by layout
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0

    # error handling and early response hang off an activity, not a sequence
    catch: Optional["Catch"] = None
    respond_early: Optional["IntermediateReturn"] = None

    kind = "node"
    terminal = False                 # does control stop here?


@dataclass
class Trigger(Node):
    trigger_type: str = "ManualTrigger"
    config: Dict[str, Any] = field(default_factory=dict)
    # Manual Trigger only: the parameter definitions (ManualTriggerJson)
    manual_parameters: List[Dict[str, Any]] = field(default_factory=list)
    should_not_log_parameters: Optional[bool] = None
    # Conditional Trigger only: the condition Subprocess, by name (bound per
    # Tenant like any Subprocess; written into config.processGuid)
    condition_subprocess: Optional[str] = None
    kind = "trigger"


@dataclass
class InnerStart(Node):
    """Container start event (Type 13). Synthesised, never in a spec."""
    kind = "inner_start"


@dataclass
class Task(Node):
    task: str = ""                   # logical task key, e.g. "http_request"
    params: Dict[str, Any] = field(default_factory=dict)
    should_retry: bool = False
    max_retry_count: Optional[int] = None
    kind = "task"


@dataclass
class AssignVariable(Node):
    variable: str = ""
    expression: Val = field(default_factory=lambda: Val("csharp", "null"))
    return_type: Optional[str] = None
    # False: the editor's "assign to variable" toggle is off; the expression
    # is only evaluated (6.3.2 reference export, variableName "")
    assigns: bool = True
    kind = "assign"


@dataclass
class CodeTask(Node):
    expression: Val = field(default_factory=lambda: Val("csharp", "{ }"))
    statement_mode: bool = True
    variable: Optional[str] = None   # None => does not assign
    return_type: Optional[str] = None
    kind = "code"


@dataclass
class Return(Node):
    expression: Val = field(default_factory=lambda: Val("csharp", "#result"))
    kind = "return"
    terminal = True


@dataclass
class Throw(Node):
    expression: Val = field(default_factory=lambda: Val("text", "Error"))
    bypass_global_exception_handler: bool = True
    kind = "throw"
    terminal = True


@dataclass
class Decision(Node):
    condition: Val = field(default_factory=lambda: Val("csharp", "true"))
    then: List["Node"] = field(default_factory=list)
    otherwise: List["Node"] = field(default_factory=list)   # [] => merge back
    yes_label: str = "yes"
    no_label: str = "no"
    kind = "decision"

    @property
    def terminal(self) -> bool:
        """A decision is terminal only if BOTH branches terminate; then
        nothing can follow it in its sequence."""
        return bool(self.then and self.otherwise
                    and self.then[-1].terminal and self.otherwise[-1].terminal)


@dataclass
class Foreach(Node):
    item: str = "item"
    collection: Val = field(default_factory=lambda: Val("csharp", "#result"))
    body: List["Node"] = field(default_factory=list)
    kind = "foreach"


@dataclass
class While(Node):
    condition: Val = field(default_factory=lambda: Val("csharp", "false"))
    max_iterations: int = 10000
    body: List["Node"] = field(default_factory=list)
    kind = "while"


@dataclass
class Scope(Node):
    body: List["Node"] = field(default_factory=list)
    kind = "scope"


@dataclass
class Catch(Node):
    """Type 14. Reached from the guarded shape by a plain sequence flow."""
    variable: str = "error"
    handler: Optional["Node"] = None
    kind = "catch"


@dataclass
class IntermediateReturn(Node):
    """Type 17: endEvent + signalEventDefinition off an activity."""
    expression: Val = field(default_factory=lambda: Val("csharp", "#result"))
    kind = "intermediate_return"
    terminal = True


@dataclass
class CallSubprocess(Node):
    subprocess: str = ""                     # key into Process.subprocesses
    params: Dict[str, Val] = field(default_factory=dict)
    kind = "call_subprocess"


@dataclass
class Branch:
    name: str
    condition: Optional[Val]                 # None on the default branch
    steps: List["Node"] = field(default_factory=list)
    bid: Optional[str] = None                # the branch's flow id


@dataclass
class InclusiveDecision(Node):
    branches: List[Branch] = field(default_factory=list)
    default: Branch = field(default_factory=lambda: Branch("Default", None))
    kind = "inclusive"

    @property
    def terminal(self) -> bool:
        allb = self.branches + [self.default]
        return all(b.steps and b.steps[-1].terminal for b in allb)


@dataclass
class SharedState(Node):
    operation: str = "AddOrUpdate"
    key: Val = field(default_factory=lambda: Val("text", ""))
    value: Val = field(default_factory=lambda: Val("csharp", "null"))
    ttl_value: Any = "1"
    ttl_multiplier: int = 60
    throw_if_false: bool = True
    global_scope: bool = False
    kind = "shared_state"


@dataclass
class DmnTable:
    inputs: List[Dict[str, str]] = field(default_factory=list)   # expression, type, name
    output: str = "Result"
    rules: List[Dict[str, Any]] = field(default_factory=list)    # when: [..], then: str
    raw_xml: Optional[str] = None            # lifted verbatim when not regenerable
    raw_parameters: Optional[str] = None


@dataclass
class Dmn(Node):
    table: DmnTable = field(default_factory=DmnTable)
    kind = "dmn"


@dataclass
class AiConnector(Node):
    params: Dict[str, Any] = field(default_factory=dict)          # raw Parameters
    kind = "ai_connector"


@dataclass
class Checkpoint(Node):
    correlation_id: Val = field(default_factory=lambda: Val("csharp", "#process.executionid"))
    ttl_minutes: int = 1440
    continue_execution: bool = False
    kind = "checkpoint"


@dataclass
class SignalResume(Node):
    correlation_id: Val = field(default_factory=lambda: Val("csharp", "#process.executionid"))
    kind = "signal_resume"


@dataclass
class ScheduledResume(Node):
    max_iterations: int = 1
    interval_minutes: int = 60
    kind = "scheduled_resume"


@dataclass
class WaitGate(Node):
    """Exclusive Decision closing a Checkpoint loop: yes continues, the
    default branch runs a Scheduled Resume that flows back to `checkpoint`."""
    condition: Val = field(default_factory=lambda: Val("csharp", "true"))
    checkpoint: Optional[Checkpoint] = None
    resume: ScheduledResume = field(default_factory=ScheduledResume)
    yes_label: str = "yes"
    no_label: str = "no"
    kind = "wait_gate"


@dataclass
class SubprocessRef:
    """A Subprocess the Process calls, as the target Tenant knows it."""
    name: str
    guid: str
    manual_triggers_json: str                # verbatim from LinkedSubProcess
    parameters: List[str] = field(default_factory=list)


@dataclass
class UnhandledErrorCall:
    subprocess: str
    params: Dict[str, Val] = field(default_factory=dict)


@dataclass
class Flow:
    """A sequence flow. Also gets its id allocated exactly once."""
    src: Node
    tgt: Node
    label: Optional[str] = None
    is_default: Optional[bool] = None
    bid: Optional[str] = None
    waypoints: List[tuple] = field(default_factory=list)
    ep_type: Optional[int] = None            # 4 exclusive branch, 16 inclusive
    condition: Optional[Val] = None          # inclusive branch expression


@dataclass
class ProcessVariable:
    name: str
    value: str                      # a JSON value, e.g. '""', '5', '[]'
    is_secret: bool = False
    mode: str = "text"
    description: str = ""


@dataclass
class Process:
    name: str
    trigger: Trigger
    body: List[Node] = field(default_factory=list)
    variables: List[ProcessVariable] = field(default_factory=list)
    description: str = ""
    unique_identifier: Optional[str] = None
    modifier: str = "frendsgen"
    major_version: int = 1
    minor_version: int = 0
    extra_triggers: List[Trigger] = field(default_factory=list)
    subprocesses: Dict[str, SubprocessRef] = field(default_factory=dict)
    on_unhandled_error: Optional[UnhandledErrorCall] = None
    preserve_references_at_checkpoint: Optional[bool] = None
    target: str = "legacy"                   # "legacy" (5.7/6.0 form) or "6.3"
    # A Subprocess: IsSubprocess true, one Manual Trigger whose parameters are
    # what callers pass. Nothing else about its export is known to differ.
    is_subprocess: bool = False

    @property
    def triggers(self) -> List[Trigger]:
        return [self.trigger] + list(self.extra_triggers)


CONTAINER_KINDS = {"foreach", "while", "scope"}


def children_sequences(n: Node):
    """The nested sequences a node owns, in emission order."""
    if n.kind == "decision":
        return [n.then, n.otherwise]
    if n.kind == "inclusive":
        return [b.steps for b in n.branches] + [n.default.steps]
    if n.kind in CONTAINER_KINDS:
        return [n.body]
    return []


def walk(seq: List[Node]):
    """Every node in a sequence tree, including catch handlers."""
    for n in seq:
        yield n
        if n.catch is not None:
            yield n.catch
            if n.catch.handler is not None:
                yield from walk([n.catch.handler])
        if n.respond_early is not None:
            yield n.respond_early
        if n.kind == "wait_gate":
            yield n.resume
        for sub in children_sequences(n):
            yield from walk(sub)
