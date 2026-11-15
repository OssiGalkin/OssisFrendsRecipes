"""Turn a Process IR into a flat, laid-out plan.

The plan is *the* single node list. Ids are allocated here, exactly once per
node and per flow, before anything is emitted. emit.py then makes one walk
over this list and appends to the BPMN buffer and the ElementParameters list
in the same step, so the two representations cannot diverge.
"""

import random
import string
from dataclasses import dataclass, field
from typing import List, Optional, Dict

from .ir import (Node, Flow, Process, Trigger, InnerStart, Return, Decision,
                 SpecError, Val, children_sequences, CONTAINER_KINDS)

# Which shapes a Catch / an Intermediate Return may hang off.
# Catch: Task, Scope and Call Subprocess. A Foreach or While cannot have one:
# wrap it in a Scope.
CATCH_HOSTS = {"task", "scope", "call_subprocess"}
# Intermediate Return: the docs list Task, Call Subprocess, Assign Variable
# and Code Task.
RESPOND_EARLY_HOSTS = {"task", "call_subprocess", "assign", "code"}
from .shapes import KIND_PREFIX


@dataclass
class Plan:
    process: Process
    nodes: List[Node] = field(default_factory=list)     # emission order
    flows: List[Flow] = field(default_factory=list)
    parent: Dict[int, Optional[Node]] = field(default_factory=dict)
    seq_of: Dict[int, List[Node]] = field(default_factory=dict)

    def parent_of(self, n: Node) -> Optional[Node]:
        return self.parent[id(n)]


class _Ids:
    def __init__(self, seed: int):
        self.rnd = random.Random(seed)
        self.used = set()

    def new(self, prefix: str) -> str:
        while True:
            suffix = "".join(self.rnd.choice(string.digits + string.ascii_lowercase)
                             for _ in range(7))
            cand = f"{prefix}_{suffix}"
            if cand not in self.used:
                self.used.add(cand)
                return cand

    def reserve(self, name: str) -> str:
        self.used.add(name)
        return name


# --------------------------------------------------------------------------
# 1. collect: create synthetic nodes, allocate ids, build the flat list
# --------------------------------------------------------------------------

def _normalise(seq: List[Node], *, must_terminate: bool, where: str):
    """Containers and the process body must end in a terminal shape.
    A missing Return is appended; nothing else is ever inferred."""
    if not seq:
        raise SpecError(f"{where}: empty sequence")
    if must_terminate and not seq[-1].terminal:
        seq.append(Return(expression=Val("csharp", "#result")))


def _register(plan: Plan, n: Node, parent: Optional[Node], seq, ids: _Ids):
    plan.parent[id(n)] = parent
    plan.seq_of[id(n)] = seq
    if n.bid is None:
        n.bid = ids.new(KIND_PREFIX[n.kind])
    else:
        ids.reserve(n.bid)
    plan.nodes.append(n)


def _collect(plan: Plan, seq: List[Node], parent: Optional[Node], ids: _Ids):
    for n in seq:
        _register(plan, n, parent, seq, ids)
        if n.kind in CONTAINER_KINDS:
            if not (n.body and n.body[0].kind == "inner_start"):
                start = InnerStart()
                start.bid = getattr(n, "inner_bid", None)
                _normalise(n.body, must_terminate=True, where=f"body of {n.name!r}")
                n.body.insert(0, start)
            _collect(plan, n.body, n, ids)
        elif n.kind in ("decision", "inclusive"):
            for sub in children_sequences(n):
                if sub:
                    _collect(plan, sub, parent, ids)
        elif n.kind == "wait_gate":
            _register(plan, n.resume, parent, seq, ids)
        if n.catch is not None and n.respond_early is not None:
            raise SpecError(
                f"{n.kind} {n.name!r}: the Task reference allows one flow out "
                f"\"with optionally an Intermediate Return or Catch shape\" in "
                f"addition, not both. Wrap the shape in a Scope and catch there.")
        if n.catch is not None:
            if n.kind not in CATCH_HOSTS:
                raise SpecError(
                    f"{n.kind} {n.name!r}: a Catch can guard a Task, a Scope or "
                    f"a Call Subprocess, not a Foreach or While; "
                    f"wrap the loop in a Scope and put the Catch on the Scope.")
            if n.catch.handler is None:
                raise SpecError(f"{n.name!r}: on_error needs exactly one handler shape")
            if n.catch.handler.terminal:
                raise SpecError(
                    f"{n.name!r}: the Catch handler ends the Process. Frends refuses "
                    f"that on import: the Catch must rejoin where {n.name!r} goes on "
                    f"success.")
            _register(plan, n.catch, parent, seq, ids)
            _collect(plan, [n.catch.handler], parent, ids)
        if n.respond_early is not None:
            if n.kind not in RESPOND_EARLY_HOSTS:
                raise SpecError(
                    f"{n.kind} {n.name!r}: an Intermediate Return can only follow "
                    f"a Task, Call Subprocess, Assign Variable or Code Task")
            _register(plan, n.respond_early, parent, seq, ids)


# --------------------------------------------------------------------------
# 2. wire: sequence flows
# --------------------------------------------------------------------------

def _wire(plan: Plan, seq: List[Node], exit_to: Optional[Node], ids: _Ids,
          where: str):
    for i, n in enumerate(seq):
        nxt = seq[i + 1] if i + 1 < len(seq) else exit_to

        if n.kind == "decision":
            yes_target = n.then[0] if n.then else nxt
            no_target = n.otherwise[0] if n.otherwise else nxt
            if yes_target is None or no_target is None:
                raise SpecError(
                    f"{where}: decision {n.name!r} has a branch that merges back "
                    f"but nothing follows the decision in its sequence. Give the "
                    f"branch a terminating shape (return/throw) or add a step "
                    f"after the decision.")
            _flow(plan, ids, n, yes_target, label=n.yes_label, is_default=False,
                  bid=getattr(n, "yes_bid", None))
            _flow(plan, ids, n, no_target, label=n.no_label, is_default=True,
                  bid=getattr(n, "no_bid", None))
            if n.then:
                _wire(plan, n.then, nxt, ids, f"{where} > {n.name!r} yes-branch")
            if n.otherwise:
                _wire(plan, n.otherwise, nxt, ids, f"{where} > {n.name!r} else-branch")
            continue

        if n.kind == "inclusive":
            for b in n.branches + [n.default]:
                tgt = b.steps[0] if b.steps else nxt
                if tgt is None:
                    raise SpecError(
                        f"{where}: inclusive decision {n.name!r} branch {b.name!r} "
                        f"merges back but nothing follows the decision.")
                _flow(plan, ids, n, tgt, label=b.name,
                      is_default=(b is n.default), ep_type=16,
                      condition=b.condition or Val("csharp", ""), bid=b.bid)
                if b.steps:
                    _wire(plan, b.steps, nxt, ids, f"{where} > {n.name!r} {b.name!r}")
            continue

        if n.kind == "wait_gate":
            if nxt is None:
                raise SpecError(f"{where}: wait_until {n.name!r} must be followed "
                                f"by a step")
            _flow(plan, ids, n, nxt, label=n.yes_label, is_default=False,
                  bid=getattr(n, "yes_bid", None))
            _flow(plan, ids, n, n.resume, label=n.no_label, is_default=True,
                  bid=getattr(n, "no_bid", None))
            _flow(plan, ids, n.resume, n.checkpoint)        # the back edge
            continue

        if n.kind in CONTAINER_KINDS:
            # container body: inner start -> ... -> inner Return
            _wire(plan, n.body, None, ids, f"{where} > {n.name!r} body")

        if not n.terminal:
            if nxt is None:
                raise SpecError(
                    f"{where}: {n.kind} {n.name!r} is the last shape but is not a "
                    f"terminating shape. End the sequence with a return or throw.")
            _flow(plan, ids, n, nxt)

        if n.catch is not None:
            h = n.catch.handler
            _flow(plan, ids, n, n.catch)
            _flow(plan, ids, n.catch, h)
            if not h.terminal and nxt is None:
                raise SpecError(f"{where}: the Catch on {n.name!r} must rejoin "
                                f"the step after it, and there is none")
            # the handler rejoins right after the guarded shape (docs: "there
            # can be no shapes in between")
            _wire(plan, [h], nxt, ids, f"{where} > {n.name!r} on_error")

        if n.respond_early is not None:
            _flow(plan, ids, n, n.respond_early)


def _flow(plan: Plan, ids: _Ids, src: Node, tgt: Node,
          label: Optional[str] = None, is_default: Optional[bool] = None,
          ep_type: Optional[int] = None, condition=None,
          bid: Optional[str] = None):
    f = Flow(src=src, tgt=tgt, label=label, is_default=is_default)
    f.ep_type = ep_type if ep_type is not None else (4 if is_default is not None
                                                       else None)
    f.condition = condition
    f.bid = ids.reserve(bid) if bid else ids.new("Flow")
    plan.flows.append(f)
    return f


# --------------------------------------------------------------------------
# 3. layout and routing
# --------------------------------------------------------------------------
# Placement and routing are NOT done here. They are delegated to the diagram
# layout engine (frendsdiagram.generate.build_layout), which was derived
# from and round-tripped against all 77 public templates, and which the
# diagram-only generator also uses. There is one layout engine in this package.
#
# What stays here is identity: the engine is driven from THIS node list, keyed
# by the ids allocated above, and only returns geometry. It never sees or
# invents an id, so BPMN ids and ElementParameters ids still come from one
# allocation.

DIAGRAM_SHAPE = {
    "scope": "scope",
    "catch": "catch",
    "intermediate_return": "intermediate_return",
    "call_subprocess": "call_subprocess",
    "inclusive": "inclusive_decision",
    "shared_state": "shared_state_task",
    "dmn": "dmn_task",
    "ai_connector": "ai_connector",
    "checkpoint": "checkpoint",
    "signal_resume": "signal_resume",
    "scheduled_resume": "scheduled_resume",
    "wait_gate": "decision",
    "trigger": "trigger",
    "inner_start": "scope_trigger",
    "task": "task",
    "assign": "assign_variable",
    "code": "code_task",
    "decision": "decision",
    "return": "return",
    "throw": "throw",
    "foreach": "foreach",
    "while": "while",
}


def diagram_spec(plan: "Plan") -> dict:
    """The plan as a layout-free diagram spec (the diagram tools' input).

    Also the bridge the other way: write this out and `frendsdiagram`
    can validate or render the process without touching the export."""
    nodes = []
    for n in plan.nodes:
        par = plan.parent_of(n)
        d = {"id": n.bid, "shape": DIAGRAM_SHAPE[n.kind], "label": n.name or ""}
        if par is not None:
            d["parent"] = par.bid
        nodes.append(d)
    flows = [{"id": f.bid, "source": f.src.bid, "target": f.tgt.bid,
              "label": f.label or ""} for f in plan.flows]
    return {"process_id": "Process_1", "name": plan.process.name,
            "nodes": nodes, "flows": flows}


def _layout(plan: "Plan"):
    from frendsdiagram.generate import build_layout, GenError
    try:
        _nodes, pos, routes = build_layout(diagram_spec(plan))
    except GenError as exc:
        raise SpecError(f"layout: {exc}")
    for n in plan.nodes:
        p = pos[n.bid]
        n.x, n.y, n.w, n.h = p["x"], p["y"], p["w"], p["h"]
    for f in plan.flows:
        f.waypoints = [(round(x), round(y)) for x, y in routes[f.bid]]


# --------------------------------------------------------------------------

def build_plan(proc: Process, seed: int = 0) -> Plan:
    ids = _Ids(seed)
    plan = Plan(process=proc)

    for i, t in enumerate(proc.triggers):
        t.bid = ids.reserve(t.bid or ("StartEvent_1" if i == 0
                                      else ids.new("Event")))
        plan.parent[id(t)] = None
        plan.seq_of[id(t)] = proc.body
        plan.nodes.append(t)

    _normalise(proc.body, must_terminate=True, where="process body")
    _collect(plan, proc.body, None, ids)

    # every Trigger is wired to the same first shape
    for t in proc.triggers:
        _flow(plan, ids, t, proc.body[0])
    _wire(plan, proc.body, None, ids, "process body")

    _layout(plan)
    return plan
