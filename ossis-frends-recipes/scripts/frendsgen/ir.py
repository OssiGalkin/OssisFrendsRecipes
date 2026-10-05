"""Intermediate representation for a Frends Process.

The IR is a tree of *sequences*. A sequence is a list of Nodes executed
left to right. Containers (Foreach, While) and the yes/else branches of a
Decision hold nested sequences.

Deliberate limits (see README):
  * one start event per process
  * no arbitrary merges: an else-branch either terminates or merges back to
    the step immediately after the decision
  * no boundary events (Scope + Catch is out of scope)

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
VALID_MODES = {"text", "csharp", "select", "toggle", "integer", "json", "xml", "sql"}


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

    kind = "node"
    terminal = False                 # does control stop here?


@dataclass
class Trigger(Node):
    trigger_type: str = "ManualTrigger"
    config: Dict[str, Any] = field(default_factory=dict)
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
class Flow:
    """A sequence flow. Also gets its id allocated exactly once."""
    src: Node
    tgt: Node
    label: Optional[str] = None
    is_default: Optional[bool] = None
    bid: Optional[str] = None
    waypoints: List[tuple] = field(default_factory=list)


@dataclass
class ProcessVariable:
    name: str
    value: str                      # a C# literal, e.g. '""' or '5'
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


CONTAINER_KINDS = {"foreach", "while"}


def children_sequences(n: Node):
    """The nested sequences a node owns, in emission order."""
    if n.kind == "decision":
        return [n.then, n.otherwise]
    if n.kind in CONTAINER_KINDS:
        return [n.body]
    return []
