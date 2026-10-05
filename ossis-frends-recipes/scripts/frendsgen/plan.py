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


def _collect(plan: Plan, seq: List[Node], parent: Optional[Node], ids: _Ids):
    for n in seq:
        plan.parent[id(n)] = parent
        plan.seq_of[id(n)] = seq
        if n.bid is None:
            n.bid = ids.new(KIND_PREFIX[n.kind])
        plan.nodes.append(n)
        if n.kind in CONTAINER_KINDS:
            start = InnerStart()
            start.bid = ids.new(KIND_PREFIX["inner_start"])
            _normalise(n.body, must_terminate=True, where=f"body of {n.name!r}")
            n.body.insert(0, start)
            _collect(plan, n.body, n, ids)
        elif n.kind == "decision":
            for sub in children_sequences(n):
                if sub:
                    _collect(plan, sub, parent, ids)


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
            _flow(plan, ids, n, yes_target, label=n.yes_label, is_default=False)
            _flow(plan, ids, n, no_target, label=n.no_label, is_default=True)
            if n.then:
                _wire(plan, n.then, nxt, ids, f"{where} > {n.name!r} yes-branch")
            if n.otherwise:
                _wire(plan, n.otherwise, nxt, ids, f"{where} > {n.name!r} else-branch")
            continue

        if n.kind in CONTAINER_KINDS:
            # container body: inner start -> ... -> inner Return
            _wire(plan, n.body, None, ids, f"{where} > {n.name!r} body")

        if n.terminal:
            continue
        if nxt is None:
            raise SpecError(
                f"{where}: {n.kind} {n.name!r} is the last shape but is not a "
                f"terminating shape. End the sequence with a return or throw.")
        _flow(plan, ids, n, nxt)


def _flow(plan: Plan, ids: _Ids, src: Node, tgt: Node,
          label: Optional[str] = None, is_default: Optional[bool] = None):
    f = Flow(src=src, tgt=tgt, label=label, is_default=is_default)
    f.bid = ids.new("Flow")
    plan.flows.append(f)
    return f


# --------------------------------------------------------------------------
# 3. layout and routing
# --------------------------------------------------------------------------
# Placement and routing are NOT done here. They are delegated to the diagram
# layout engine (frendsgen.diagram.generate.build_layout), which was derived
# from and round-tripped against all 77 public templates, and which the
# diagram-only generator also uses. There is one layout engine in this package.
#
# What stays here is identity: the engine is driven from THIS node list, keyed
# by the ids allocated above, and only returns geometry. It never sees or
# invents an id, so BPMN ids and ElementParameters ids still come from one
# allocation.

DIAGRAM_SHAPE = {
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

    Also the bridge the other way: write this out and `frendsgen.diagram`
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
    from .diagram.generate import build_layout, GenError
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

    proc.trigger.bid = ids.reserve(proc.trigger.bid or "StartEvent_1")
    plan.parent[id(proc.trigger)] = None
    plan.seq_of[id(proc.trigger)] = proc.body
    plan.nodes.append(proc.trigger)

    _normalise(proc.body, must_terminate=True, where="process body")
    _collect(plan, proc.body, None, ids)

    _flow(plan, ids, proc.trigger, proc.body[0])
    _wire(plan, proc.body, None, ids, "process body")

    _layout(plan)
    return plan
