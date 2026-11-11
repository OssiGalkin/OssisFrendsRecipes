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
                 Throw, Decision, Foreach, While, ProcessVariable, Val, SpecError,
                 Scope, Catch, IntermediateReturn, CallSubprocess, InclusiveDecision,
                 Branch, SharedState, Dmn, AiConnector, Checkpoint, SignalResume,
                 ScheduledResume, WaitGate, SubprocessRef, UnhandledErrorCall)
from .tasks import PARSERS, task_for_type_id, register_profile
from .dmn import parse_dmn


class Unliftable(Exception):
    """The export uses something the IR cannot represent."""


def _local(t: str) -> str:
    return t.split("}")[-1]


def _val(cell: Any, where: str) -> Val:
    if not isinstance(cell, dict) or set(cell) != {"mode", "value"}:
        raise Unliftable(f"{where}: expected a {{mode, value}} cell, got {cell!r}")
    return Val(cell["mode"], cell["value"])


def _target_of(proc) -> str:
    v = str(proc.get("FrendsVersion") or "")
    try:
        major, minor = (int(x) for x in v.split(".")[:2])
    except ValueError:
        return "legacy"
    return "6.3" if (major, minor) >= (6, 3) else "legacy"


def lift_process(proc: Dict[str, Any],
                 process_variables_json: Optional[str] = None,
                 linked_subprocesses: Optional[List[Dict[str, Any]]] = None) -> Process:
    eps = {e["Id"]: e for e in json.loads(proc["ElementParameters"])}
    subs: Dict[str, SubprocessRef] = {}
    by_guid: Dict[str, str] = {}
    for e in linked_subprocesses or []:
        mt = e.get("ManualTriggersJson") or "[]"
        subs[e["SubProcessName"]] = SubprocessRef(
            name=e["SubProcessName"], guid=e["SubProcessGuid"],
            manual_triggers_json=mt, parameters=[p.get("name") for p in json.loads(mt)])
        by_guid[e["SubProcessGuid"]] = e["SubProcessName"]

    def sub_key(guid: str) -> str:
        if guid not in by_guid:
            raise Unliftable(f"Subprocess {guid} is not in LinkedSubProcess")
        return by_guid[guid]

    def cells(P: Dict[str, Any], where: str) -> Dict[str, Val]:
        return {k: _val(v, f"{where}.{k}") for k, v in P.items()}
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

    trig_ids = [i for i, e in elems.items()
                if _local(e.tag) == "startEvent" and i in eps and eps[i]["Type"] == 0]
    tj = {t["id"]: t for t in json.loads(proc.get("TriggersJson") or "[]")}
    manual_params = json.loads(proc.get("ManualTriggerJson") or "[]")
    triggers = []
    for tid in trig_ids:
        t = tj.get(tid, {})
        ttype = t.get("$type") or eps[tid]["SelectedTypeId"]
        tr = Trigger(name=t.get("name") or eps[tid]["Name"], trigger_type=ttype,
                     config=t.get("config") or {},
                     should_not_log_parameters=t.get("shouldNotLogParameters"))
        if ttype == "ManualTrigger":
            tr.manual_parameters = manual_params
            if manual_params:
                tr.config = {}
        if ttype == "ConditionalTrigger" and tr.config.get("processGuid"):
            tr.config = dict(tr.config)
            tr.condition_subprocess = sub_key(tr.config["processGuid"])
            tr.config["processGuid"] = ""
        tr.bid = tid
        triggers.append(tr)
    if not triggers:
        raise Unliftable("no Trigger")
    firsts = {target[succ[t][0]] for t in trig_ids if succ.get(t)}
    if len(firsts) != 1:
        raise Unliftable(f"Triggers lead to {len(firsts)} different first shapes")

    def node_for(nid: str):
        e, el = eps[nid], elems[nid]
        t, P, name = e["Type"], e["Parameters"], e["Name"]
        if t in (5, 6, 14, 17):
            # Returns, Throws, Catches and Intermediate Returns carry their
            # name on the BPMN element, not in ElementParameters.
            name = el.get("name") or name
        common = dict(name=name, description=e.get("Description"),
                      should_not_log_result=e.get("ShouldNotLogResult"), bid=nid)
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
            if "useStatementMode" not in P:
                return AssignVariable(variable=P.get("variableName", ""),
                                      expression=expr, assigns=assigns,
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
        if t in (8, 10, 11):
            return keep_inner(more_for(t, nid, P, common, e, name))
        return more_for(t, nid, P, common, e, name)

    def more_for(t, nid, P, common, e, name):
        if t == 10:
            return Foreach(item=P["variable"],
                           collection=_val(P["expression"], nid),
                           body=lift_seq(inner_start(nid), None), **common)
        if t == 11:
            mi = (P.get("maxIterations") or {}).get("value", 10000)
            return While(condition=_val(P["expression"], nid),
                         max_iterations=int(mi),
                         body=lift_seq(inner_start(nid), None), **common)
        if t == 8:
            return Scope(body=lift_seq(inner_start(nid), None), **common)
        if t == 7:
            return CallSubprocess(subprocess=sub_key(e["SelectedTypeId"]),
                                  params=cells(P, nid), **common)
        if t == 20:
            if e["SelectedTypeId"] != "AddOrUpdate":
                raise Unliftable(f"Shared State {e['SelectedTypeId']} is not supported")
            return SharedState(operation="AddOrUpdate",
                               key=_val(P["keyExpression"], nid),
                               value=_val(P["valueExpression"], nid),
                               ttl_value=str(P["ttlValue"]["value"]),
                               ttl_multiplier=int(P["ttlMultiplier"]),
                               throw_if_false=bool(P["throwIfFalse"]),
                               global_scope=bool(P["isGlobalScope"]), **common)
        if t == 21:
            if f"decisionId_{nid}" != P.get("decisionId"):
                raise Unliftable(f"{nid}: decisionId {P.get('decisionId')!r} is not "
                                 f"decisionId_<shape id>")
            return Dmn(table=parse_dmn(P["dmnXml"], P.get("parameters") or "{}"),
                       **common)
        if t == 27:
            return AiConnector(params=P, **common)
        if t == 24:
            return Checkpoint(correlation_id=_val(P["correlationId"], nid),
                              ttl_minutes=int(P["ttlMinutes"]["value"]),
                              continue_execution=bool(P["continueExecution"]["value"]),
                              **common)
        if t == 26:
            return SignalResume(correlation_id=_val(P["correlationId"], nid), **common)
        raise Unliftable(f"shape Type {t} ({name!r}) is not in the IR")

    inner_ids: Dict[str, str] = {}

    def inner_start(container_id: str) -> str:
        starts = [c.get("id") for c in elems[container_id]
                  if _local(c.tag) == "startEvent"]
        if len(starts) != 1:
            raise Unliftable(f"{container_id}: {len(starts)} inner start events")
        inner_ids[container_id] = starts[0]
        return target[succ[starts[0]][0]]

    def keep_inner(n):
        if n.bid in inner_ids:
            n.inner_bid = inner_ids[n.bid]
        return n

    def attach(n, nid: str, outs: List[str]) -> List[str]:
        """Peel Catch / Intermediate Return flows off an activity; return the
        remaining (main-line) flows."""
        rest = []
        for f in outs:
            tid = target[f]
            tt = eps.get(tid, {}).get("Type")
            if tt == 14:
                c_outs = succ.get(tid, [])
                if len(c_outs) != 1:
                    raise Unliftable(f"{tid}: Catch with {len(c_outs)} outgoing flows")
                hid = target[c_outs[0]]
                handler = node_for(hid)
                h_outs = succ.get(hid, [])
                c = Catch(variable=eps[tid]["Parameters"].get("expression", "error"),
                          handler=handler, bid=tid,
                          name=elems[tid].get("name"))
                n.catch = c
                c._rejoin = target[h_outs[0]] if h_outs else None
            elif tt == 17:
                n.respond_early = IntermediateReturn(
                    expression=_val(eps[tid]["Parameters"]["expression"], tid),
                    bid=tid, name=elems[tid].get("name"))
            else:
                rest.append(f)
        if n.catch is not None and getattr(n.catch, "_rejoin", None) is not None:
            if [target[f] for f in rest] != [n.catch._rejoin]:
                raise Unliftable(f"{nid}: Catch handler does not rejoin at the "
                                 f"guarded shape's successor")
        return rest

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
                # Checkpoint loop: default -> Scheduled Resume -> back to the
                # Checkpoint that precedes this gateway.
                if (eps.get(no_t, {}).get("Type") == 25 and out
                        and out[-1].kind == "checkpoint"
                        and [target[f] for f in succ.get(no_t, [])] == [out[-1].bid]):
                    rp = eps[no_t]["Parameters"]
                    out.append(WaitGate(
                        condition=_val(e["Parameters"]["expression"], cur),
                        checkpoint=out[-1], name=e["Name"], bid=cur,
                        description=e.get("Description"),
                        resume=ScheduledResume(
                            max_iterations=int(rp["maxIterations"]["value"]),
                            interval_minutes=int(rp["rehydrationIntervalMinutes"]["value"]),
                            bid=no_t),
                        yes_label=eps[yes]["Name"] or "yes",
                        no_label=eps[dflt]["Name"] or "no"))
                    out[-1].yes_bid, out[-1].no_bid = yes, dflt
                    cur = yes_t
                    continue
                merge = _merge_point([yes_t, no_t])
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
                             no_label=eps[dflt]["Name"] or "no", bid=cur)
                d.yes_bid, d.no_bid = yes, dflt
                d.then = [] if yes_t == merge else lift_seq(yes_t, merge)
                d.otherwise = [] if no_t == merge else lift_seq(no_t, merge)
                out.append(d)
                cur = merge
                continue
            if e["Type"] == 15:
                outs = succ.get(cur, [])
                dflt = elems[cur].get("default")
                if dflt not in outs:
                    raise Unliftable(f"{cur}: inclusive gateway without a default flow")
                tgts = [target[f] for f in outs]
                merge = _merge_point(tgts)
                if merge is None:
                    raise Unliftable(f"{cur}: inclusive branches never rejoin")

                def branch(f):
                    fe = eps[f]
                    t0 = target[f]
                    cond = None if f == dflt else _val(fe["Parameters"]["expression"], f)
                    return Branch(fe["Name"] or ("Default" if f == dflt else f), cond,
                                  [] if t0 == merge else lift_seq(t0, merge), bid=f)
                out.append(InclusiveDecision(
                    branches=[branch(f) for f in outs if f != dflt],
                    default=branch(dflt), name=e["Name"], bid=cur,
                    description=e.get("Description")))
                cur = merge
                continue
            n = node_for(cur)
            out.append(n)
            outs = attach(n, cur, succ.get(cur, []))
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

    def _merge_point(starts: List[str]) -> Optional[str]:
        first = _reach(starts[0])
        others = [set(_reach(s)) for s in starts[1:]]
        for n in first:
            if all(n in o for o in others):
                return n
        return None

    body = lift_seq(next(iter(firsts)), None)

    variables = []
    pvj = process_variables_json or proc.get("ProcessVariablesJson")
    for name, v in json.loads(pvj or "{}").items():
        variables.append(ProcessVariable(name=name, value=v.get("Value", '""'),
                                         is_secret=bool(v.get("IsSecret")),
                                         mode=v.get("Mode", "text"),
                                         description=v.get("Description", "")))

    oue = None
    for e in eps.values():
        if e["Type"] == 18:
            oue = UnhandledErrorCall(subprocess=sub_key(e["SelectedTypeId"]),
                                     params=cells(e["Parameters"] or {}, e["Id"]))
        elif e["Type"] not in (19,) and e["Id"] not in elems:
            raise Unliftable(f"{e['Id']}: Type {e['Type']} entry with no element")

    target_form = _target_of(proc)
    if target_form != "6.3" and (len(triggers) > 1 or triggers[0].trigger_type
                                 != "ManualTrigger"):
        raise Unliftable("only the Manual Trigger exists in the legacy form")
    return Process(name=proc["Name"], description=proc.get("Description") or "",
                   modifier=proc.get("Modifier") or "frendsgen",
                   trigger=triggers[0], extra_triggers=triggers[1:],
                   variables=variables, body=body,
                   major_version=proc.get("MajorVersion", 1),
                   minor_version=proc.get("MinorVersion", 0),
                   subprocesses=subs, on_unhandled_error=oue,
                   preserve_references_at_checkpoint=proc.get(
                       "PreserveReferencesAtCheckpoint"),
                   target=target_form,
                   is_subprocess=bool(proc.get("IsSubprocess")))


def lift_file(path: str) -> List[Process]:
    doc = json.load(open(path, encoding="utf-8-sig"))
    register_profile(doc)      # learn this installation's task GUIDs
    if "ProcessTemplates" in doc:
        out = []
        for t in doc["ProcessTemplates"]:
            info = t["ProcessInfo"]
            p = info["Process"]
            out.append(lift_process(p, t.get("ProcessVariablesJson"),
                                    (info.get("LinkedSubProcess") or {}).get(
                                        p["UniqueIdentifier"])))
        return out
    return [lift_process(p, None, (doc.get("LinkedSubProcess") or {}).get(
        p["UniqueIdentifier"])) for p in doc.get("Processes", [])]
