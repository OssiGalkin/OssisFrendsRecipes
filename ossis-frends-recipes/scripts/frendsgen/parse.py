"""Reverse parser: a real Frends export -> IR.

Not optional. It is what makes the strong tests possible:
  * rebuild real task parameters and diff against what Frends wrote;
  * lift whole real Processes into the IR, regenerate, and compare.
It also finds emitter and loader bugs the forward path cannot reach, because
the input is Frends' own output rather than the tool's.
"""

import json
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from .ir import (Process, Trigger, Task, AssignVariable, CodeTask, Return,
                 Throw, Decision, Foreach, While, ProcessVariable, Val, SpecError)
from .tasks import PARSERS, task_for_type_id, register_profile


class Unliftable(Exception):
    """The export uses something the IR cannot represent."""


def _local(t: str) -> str:
    return t.split("}")[-1]


def _val(cell: Any, where: str) -> Val:
    if not isinstance(cell, dict) or set(cell) != {"mode", "value"}:
        raise Unliftable(f"{where}: expected a {{mode, value}} cell, got {cell!r}")
    return Val(cell["mode"], cell["value"])


def lift_process(proc: Dict[str, Any],
                 process_variables_json: Optional[str] = None) -> Process:
    eps = {e["Id"]: e for e in json.loads(proc["ElementParameters"])}
    root = ET.fromstring(proc["Bpmn"])
    proc_el = next(c for c in root if _local(c.tag) == "process")

    elems: Dict[str, ET.Element] = {}
    kids: Dict[Optional[str], List[str]] = {}

    def index(el, parent):
        kids.setdefault(parent, [])
        for c in el:
            cid, tag = c.get("id"), _local(c.tag)
            if cid and tag not in ("BPMNShape", "BPMNEdge", "BPMNLabel"):
                elems[cid] = c
                kids[parent].append(cid)
                index(c, cid if tag == "subProcess" else parent)
            else:
                index(c, parent)

    index(proc_el, None)

    flows = [(i, e.get("sourceRef"), e.get("targetRef"))
             for i, e in elems.items() if _local(e.tag) == "sequenceFlow"]
    succ: Dict[str, List[str]] = {}
    for fid, s, t in flows:
        succ.setdefault(s, []).append(fid)
    target = {fid: t for fid, s, t in flows}

    trig_id = next(i for i, e in elems.items()
                   if _local(e.tag) == "startEvent" and eps[i]["Type"] == 0)
    tj = json.loads(proc.get("TriggersJson") or "[]")
    ttype = tj[0]["$type"] if tj else eps[trig_id]["SelectedTypeId"]
    if ttype != "ManualTrigger":
        raise Unliftable(f"trigger {ttype} is not supported")

    def node_for(nid: str):
        e, el = eps[nid], elems[nid]
        t, P, name = e["Type"], e["Parameters"], e["Name"]
        if t in (5, 6):
            # Returns and Throws carry their name on the BPMN element, not in
            # ElementParameters.
            name = el.get("name") or name
        common = dict(name=name, description=e.get("Description"),
                      should_not_log_result=e.get("ShouldNotLogResult"))
        if t == 1:
            key = task_for_type_id(e["SelectedTypeId"])
            if key is None:
                raise Unliftable(f"unsupported task {e['SelectedTypeId']}")
            return Task(task=key, params=PARSERS[key](P),
                        should_retry=bool(e.get("ShouldRetry")),
                        max_retry_count=e.get("MaxRetryCount"), **common)
        if t == 12:
            expr = _val(P["variableExpression"], nid)
            stmt = bool((P.get("useStatementMode") or {}).get("value"))
            assigns = bool((P.get("shouldAssignVariable") or {}).get("value"))
            # An Assign Variable has no useStatementMode key at all: 135 of 138
            # 30x30 scriptTasks in the corpus omit it, and 37 of 37 100x80 ones
            # carry it. The value is not the discriminator; the key is.
            if "useStatementMode" not in P and assigns:
                return AssignVariable(variable=P.get("variableName", ""),
                                      expression=expr,
                                      return_type=P.get("returnType"), **common)
            return CodeTask(expression=expr, statement_mode=stmt,
                            variable=P.get("variableName") if assigns else None,
                            return_type=P.get("returnType"), **common)
        if t == 5:
            if e["SelectedTypeId"] not in (None, "None"):
                raise Unliftable(f"Return of type {e['SelectedTypeId']} unsupported")
            return Return(expression=_val(P["expression"], nid), **common)
        if t == 6:
            if e["SelectedTypeId"] not in (None, "None"):
                raise Unliftable(f"Throw of type {e['SelectedTypeId']} unsupported")
            bg = (P.get("bypassGlobalExceptionHandler") or {}).get("value", True)
            return Throw(expression=_val(P["expression"], nid),
                         bypass_global_exception_handler=bool(bg), **common)
        if t == 10:
            return Foreach(item=P["variable"],
                           collection=_val(P["expression"], nid),
                           body=lift_seq(inner_start(nid), None), **common)
        if t == 11:
            mi = (P.get("maxIterations") or {}).get("value", 10000)
            return While(condition=_val(P["expression"], nid),
                         max_iterations=int(mi),
                         body=lift_seq(inner_start(nid), None), **common)
        raise Unliftable(f"shape Type {t} ({name!r}) is not in the IR")

    def inner_start(container_id: str) -> str:
        starts = [c.get("id") for c in elems[container_id]
                  if _local(c.tag) == "startEvent"]
        if len(starts) != 1:
            raise Unliftable(f"{container_id}: {len(starts)} inner start events")
        return target[succ[starts[0]][0]]

    def lift_seq(start: Optional[str], stop: Optional[str]) -> List:
        out = []
        cur = start
        while cur is not None and cur != stop:
            e = eps[cur]
            if e["Type"] == 2:
                outs = succ.get(cur, [])
                if len(outs) != 2:
                    raise Unliftable(f"{cur}: gateway with {len(outs)} outgoing flows")
                dflt = elems[cur].get("default")
                yes = next(f for f in outs if f != dflt)
                yes_t, no_t = target[yes], target[dflt]
                merge = _merge_point(yes_t, no_t)
                if merge is None:
                    # The branches never rejoin, so both end in terminal
                    # shapes and neither is graph-theoretically "the main
                    # line". Convention, matching how Frends models are
                    # actually drawn: the default (else) branch is the
                    # branch, and the yes path continues in the enclosing
                    # sequence. Re-emitting this produces the same graph.
                    merge = yes_t
                    if not _reach(no_t):
                        raise Unliftable(f"{cur}: default flow leads nowhere")
                d = Decision(condition=_val(e["Parameters"]["expression"], cur),
                             name=e["Name"], description=e.get("Description"),
                             yes_label=eps[yes]["Name"] or "yes",
                             no_label=eps[dflt]["Name"] or "no")
                d.then = [] if yes_t == merge else lift_seq(yes_t, merge)
                d.otherwise = [] if no_t == merge else lift_seq(no_t, merge)
                out.append(d)
                cur = merge
                continue
            out.append(node_for(cur))
            outs = succ.get(cur, [])
            if not outs:
                break
            if len(outs) > 1:
                raise Unliftable(f"{cur}: {len(outs)} outgoing flows from a "
                                 f"non-gateway shape")
            cur = target[outs[0]]
        return out

    def _reach(nid: Optional[str]):
        seen, stack = [], [nid]
        while stack:
            n = stack.pop(0)
            if n is None or n in seen:
                continue
            seen.append(n)
            for f in succ.get(n, []):
                stack.append(target[f])
        return seen

    def _merge_point(a: str, b: str) -> Optional[str]:
        ra, rb = _reach(a), set(_reach(b))
        for n in ra:
            if n in rb:
                return n
        return None

    body = lift_seq(target[succ[trig_id][0]], None)

    variables = []
    pvj = process_variables_json or proc.get("ProcessVariablesJson")
    for name, v in json.loads(pvj or "{}").items():
        variables.append(ProcessVariable(name=name, value=v.get("Value", '""'),
                                         is_secret=bool(v.get("IsSecret")),
                                         mode=v.get("Mode", "text"),
                                         description=v.get("Description", "")))

    return Process(name=proc["Name"], description=proc.get("Description") or "",
                   modifier=proc.get("Modifier") or "frendsgen",
                   trigger=Trigger(name=(tj[0]["name"] if tj else "Manual"),
                                   trigger_type="ManualTrigger",
                                   config=(tj[0]["config"] if tj else {})),
                   variables=variables, body=body,
                   major_version=proc.get("MajorVersion", 1),
                   minor_version=proc.get("MinorVersion", 0))


def lift_file(path: str) -> List[Process]:
    doc = json.load(open(path, encoding="utf-8-sig"))
    register_profile(doc)      # learn this installation's task GUIDs
    if "ProcessTemplates" in doc:
        return [lift_process(t["ProcessInfo"]["Process"], t.get("ProcessVariablesJson"))
                for t in doc["ProcessTemplates"]]
    return [lift_process(p) for p in doc.get("Processes", [])]
