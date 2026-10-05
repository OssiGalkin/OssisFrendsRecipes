"""Emitter.

One walk over plan.nodes + plan.flows produces, in the same step:
  * the BPMN element for each node/flow,
  * its ElementParameters entry,
  * its BPMNShape / BPMNEdge.
All three read `n.bid` off the same object. Nothing is matched up by name or
position afterwards, so the representations cannot drift apart.
"""

import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .ir import Process, Node, Flow, SpecError, CONTAINER_KINDS
from .plan import Plan, build_plan
from .shapes import KIND_TYPE, TYPE_TAG, CONTAINER_LOOP, EP_KEYS
from .tasks import BUILDERS, binding, DEFAULT_PROFILE

HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<bpmn2:definitions xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    'xmlns:bpmn2="http://www.omg.org/spec/BPMN/20100524/MODEL" '
    'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" '
    'xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" '
    'xmlns:di="http://www.omg.org/spec/DD/20100524/DI" '
    'id="sample-diagram" targetNamespace="http://bpmn.io/schema/bpmn" '
    'xsi:schemaLocation="http://www.omg.org/spec/BPMN/20100524/MODEL BPMN20.xsd">'
)
EXPORT_VERSION = "Acc41"


def _upper_guid(task_ref: str) -> str:
    parts = task_ref.split("/")
    if len(parts) > 2:
        parts[2] = parts[2].upper()
    return "/".join(parts)


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _ep(node_or_flow, type_no: int, params: Dict[str, Any], **over) -> Dict[str, Any]:
    e = {
        "Id": node_or_flow.bid, "Type": type_no, "Parameters": params,
        "SelectedTypeId": None, "PromoteResultAs": None,
        "Name": getattr(node_or_flow, "name", None) or None,
        "Description": getattr(node_or_flow, "description", None),
        "IsDefault": None, "ShouldRetry": None, "MaxRetryCount": None,
        "ShouldNotLogResult": getattr(node_or_flow, "should_not_log_result", None),
        "ShouldDispose": None,
    }
    e.update(over)
    return {k: e[k] for k in EP_KEYS}      # corpus key order, 2108/2108


class _Emitted:
    def __init__(self):
        self.tag = ""
        self.attrs: Dict[str, str] = {}
        self.extras: List[str] = []       # loopCharacteristics, eventDefinition
        self.parent: str = ""


# Six fields are null in all 77 corpus templates. The Process import path
# rejects at least GraphJson with an NHibernate not-null error:
#   "not-null property references a null or transient value
#    Frends.Management.Web.Models.Dtos.Process.GraphJson"
# The Template path accepts null for all six, which is why the corpus never
# shows what they should contain. NULLABLE_IN_CORPUS lists them; `overrides`
# lets a caller fill them. No value here is verified — see README.
NULLABLE_IN_CORPUS = ("GraphJson", "TagString", "AssemblyName", "PackageId",
                      "PackageVersion", "ProcessVariablesJson")

# GraphJson is the legacy Frends 4.2 graph representation. Three import
# results pin it down on the ProcessExport path:
#   null  -> "not-null property references a null or transient value ...
#             Process.GraphJson"
#   ""    -> imports (verified once)
#   "{}"  -> "Old frends 4.2 type Processes are not longer supported."
# So the field must be present and empty: present satisfies the column,
# empty tells Frends this is a BPMN process rather than a 4.2 graph one.
# The Template path accepts null, which is why all 77 corpus templates have
# it and why the corpus cannot show you this.
GRAPH_JSON_PROCESS_FORM = ""


def emit(proc: Process, seed: int = 0,
         overrides: Optional[Dict[str, Any]] = None,
         profile: str = DEFAULT_PROFILE) -> Dict[str, Any]:
    plan = build_plan(proc, seed=seed)

    element_parameters: List[Dict[str, Any]] = []
    parts: Dict[str, _Emitted] = {}
    children: Dict[str, List[str]] = defaultdict(list)
    incoming: Dict[str, List[str]] = defaultdict(list)
    outgoing: Dict[str, List[str]] = defaultdict(list)
    di_shapes: List[str] = []
    di_edges: List[str] = []
    used_tasks: List[str] = []
    linked_tasks: List[Dict[str, Any]] = []

    for f in plan.flows:
        outgoing[f.src.bid].append(f.bid)
        incoming[f.tgt.bid].append(f.bid)

    # ---- the one walk -----------------------------------------------------
    for n in plan.nodes:
        t = KIND_TYPE[n.kind]
        e = _Emitted()
        e.tag = TYPE_TAG[t]
        e.attrs = {"id": n.bid}
        if n.name:
            e.attrs["name"] = n.name
        par = plan.parent_of(n)
        e.parent = par.bid if par is not None else "Process_1"

        if n.kind == "trigger":
            element_parameters.append(_ep(n, t, dict(n.config),
                                          SelectedTypeId=n.trigger_type))

        elif n.kind == "inner_start":
            element_parameters.append(_ep(n, t, {}, SelectedTypeId="", Name=None))

        elif n.kind == "task":
            if n.task not in BUILDERS:
                raise SpecError(
                    f"unsupported task {n.task!r}. Supported: {sorted(BUILDERS)}. "
                    f"Adding one requires a parameter schema checked against real "
                    f"exports of that task.")
            meta = binding(n.task, profile)
            element_parameters.append(_ep(
                n, t, BUILDERS[n.task](n.params),
                SelectedTypeId=meta["selected_type_id"],
                ShouldRetry=bool(n.should_retry),
                MaxRetryCount=n.max_retry_count if n.should_retry else None))
            if meta["selected_type_id"] not in used_tasks:
                used_tasks.append(meta["selected_type_id"])
                linked_tasks.append(meta["linked"])
            if n.should_retry:
                # 40/40 retrying tasks in the corpus carry this marker;
                # 265/265 non-retrying ones do not.
                e.extras.append("<bpmn2:standardLoopCharacteristics />")

        elif n.kind == "assign":
            element_parameters.append(_ep(n, t, {
                "variableName": n.variable,
                "variableExpression": n.expression.json(),
                "shouldAssignVariable": {"mode": "toggle", "value": True},
                **({"returnType": n.return_type} if n.return_type is not None else {}),
            }))

        elif n.kind == "code":
            p: Dict[str, Any] = {"useStatementMode": {"mode": "toggle",
                                                      "value": bool(n.statement_mode)}}
            if n.variable:
                p["variableName"] = n.variable
            p["variableExpression"] = n.expression.json()
            p["shouldAssignVariable"] = {"mode": "toggle", "value": bool(n.variable)}
            if n.return_type is not None:
                p["returnType"] = n.return_type
            element_parameters.append(_ep(n, t, p))

        elif n.kind == "return":
            # A Return's display name lives in the BPMN name attribute only;
            # ElementParameters.Name is null in 209 of 210 corpus Returns.
            element_parameters.append(
                _ep(n, t, {"expression": n.expression.json()}, Name=None))

        elif n.kind == "throw":
            # Same for Throw: 112 of 113 corpus Throws have a BPMN name and
            # a null ElementParameters.Name.
            element_parameters.append(_ep(n, t, {
                "expression": n.expression.json(),
                "bypassGlobalExceptionHandler": {
                    "mode": "toggle", "value": bool(n.bypass_global_exception_handler)},
            }, Name=None))
            # id format taken from the tenant export: the element id, whole.
            e.extras.append(f'<bpmn2:signalEventDefinition '
                            f'id="SignalEventDefinition_{n.bid}" />')

        elif n.kind == "decision":
            element_parameters.append(_ep(n, t, {"expression": n.condition.json()}))
            dflt = next(f for f in plan.flows if f.src is n and f.is_default)
            e.attrs["default"] = dflt.bid   # 286/286 gateways carry this

        elif n.kind in CONTAINER_KINDS:
            if n.kind == "foreach":
                params = {"variable": n.item, "expression": n.collection.json()}
            else:
                params = {"maxIterations": {"mode": "integer",
                                            "value": str(n.max_iterations)},
                          "expression": n.condition.json()}
            element_parameters.append(_ep(n, t, params))
            tag, attrs = CONTAINER_LOOP[t]
            a = "".join(f' {k}="{v}"' for k, v in attrs.items())
            e.extras.append(f"<bpmn2:{tag}{a} />")

        else:
            raise SpecError(f"no emitter for IR kind {n.kind!r}")

        parts[n.bid] = e
        di_shapes.append(_di_shape(n, t))

    for f in plan.flows:
        e = _Emitted()
        e.tag = "sequenceFlow"
        e.attrs = {"id": f.bid, "sourceRef": f.src.bid, "targetRef": f.tgt.bid}
        if f.label:
            e.attrs["name"] = f.label
        par = plan.parent_of(f.src)
        e.parent = par.bid if par is not None else "Process_1"
        parts[f.bid] = e
        # Frends writes an ElementParameters entry for a sequence flow only
        # when it leaves a decision gateway (575/575 in the corpus; the other
        # 697 flows have no entry at all).
        if f.is_default is not None:
            element_parameters.append(
                _ep(f, 4, {}, Name=f.label or None, IsDefault=bool(f.is_default)))
        di_edges.append(_di_edge(f))

    # ---- assemble ---------------------------------------------------------
    for bid, e in parts.items():
        children[e.parent].append(bid)

    def render(bid: str) -> str:
        e = parts[bid]
        attrs = "".join(f' {k}="{_esc(v)}"' for k, v in e.attrs.items())
        inner = "".join(f"<bpmn2:incoming>{i}</bpmn2:incoming>" for i in incoming[bid])
        inner += "".join(f"<bpmn2:outgoing>{o}</bpmn2:outgoing>" for o in outgoing[bid])
        inner += "".join(e.extras)
        inner += "".join(render(c) for c in children.get(bid, []))
        if not inner:
            return f"<bpmn2:{e.tag}{attrs} />"
        return f"<bpmn2:{e.tag}{attrs}>{inner}</bpmn2:{e.tag}>"

    body = "".join(render(b) for b in children["Process_1"])
    bpmn = (HEADER + '<bpmn2:process id="Process_1" isExecutable="false">' + body +
            "</bpmn2:process>" +
            '<bpmndi:BPMNDiagram id="BPMNDiagram_1">'
            '<bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Process_1">' +
            "".join(di_shapes) + "".join(di_edges) +
            "</bpmndi:BPMNPlane></bpmndi:BPMNDiagram></bpmn2:definitions>")

    guid = proc.unique_identifier or str(uuid.uuid4())
    triggers = [{"$type": proc.trigger.trigger_type, "config": dict(proc.trigger.config),
                 "name": proc.trigger.name or "Manual", "id": proc.trigger.bid,
                 "shouldNotLogParameters": None}]
    pv = {v.name: {"Value": v.value, "IsSecret": v.is_secret, "Mode": v.mode,
                   "Description": v.description} for v in proc.variables}

    process = {
        "Name": proc.name,
        "Modified": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f"),
        "Modifier": proc.modifier or "frendsgen",   # must be non-null on import
        "TagString": None,
        "Tags": [],
        "Description": proc.description,
        "Version": 1,
        "UniqueIdentifier": guid,
        "GraphJson": None,
        "Bpmn": bpmn,
        "ElementParameters": json.dumps(element_parameters, separators=(",", ":"),
                                        ensure_ascii=False),
        "ManualTriggerJson": "[]",
        "IsSubprocess": False,
        "TriggersJson": json.dumps(triggers, separators=(",", ":"), ensure_ascii=False),
        "AssemblyName": None,
        "PackageId": None,
        "PackageVersion": None,
        # Casing differs by export path. Template exports uppercase the GUID
        # here (195/195 corpus); the tenant's own ProcessExport leaves it
        # lowercase (1/1). SelectedTypeId and LinkedTasks[].Id are lowercase
        # on both. process_export/template_export set this.
        "UsedTasksJson": json.dumps(used_tasks, separators=(",", ":")),
        "UsedSubprocessesJson": "{}",
        "ProcessExecutionVersion": "",
        "FrendsVersion": "5.7.3.1743",
        "TargetFramework": "net8.0",
        "StaticRequiredEnvironmentVariables": [],
        "RequiredEnvironmentVariables": [],
        "PromotedResultVariablesJson": "[]",
        "MajorVersion": proc.major_version,
        "MinorVersion": proc.minor_version,
        "IsForMonitoringRule": False,
        "ProcessVariablesJson": json.dumps(pv, separators=(",", ":"),
                                           ensure_ascii=False) if pv else None,
    }
    for k, v in (overrides or {}).items():
        if k not in process:
            raise SpecError(f"unknown process field override {k!r}")
        process[k] = v
    return {"process": process, "linked_tasks": linked_tasks, "plan": plan,
            "process_variables": pv}


# --- DI --------------------------------------------------------------------

def _di_shape(n: Node, t: int) -> str:
    extra = ""
    if n.kind in CONTAINER_KINDS:
        extra = ' isExpanded="true"'
    elif n.kind == "decision":
        extra = ' isMarkerVisible="true"'
    label = ""
    if n.name and n.kind in ("trigger", "return", "throw", "decision"):
        lw = max(40, min(140, 7 * len(n.name)))
        lx = round(n.x + n.w / 2 - lw / 2)
        ly = round(n.y + n.h + 5) if n.kind != "decision" else round(n.y - 25)
        label = (f'<bpmndi:BPMNLabel><dc:Bounds x="{lx}" y="{ly}" '
                 f'width="{lw}" height="14" /></bpmndi:BPMNLabel>')
    elif n.kind in ("task", "assign", "code", "foreach", "while"):
        label = "<bpmndi:BPMNLabel />"
    return (f'<bpmndi:BPMNShape id="{n.bid}_di" bpmnElement="{n.bid}"{extra}>'
            f'<dc:Bounds x="{round(n.x)}" y="{round(n.y)}" '
            f'width="{round(n.w)}" height="{round(n.h)}" /></bpmndi:BPMNShape>'
            .replace("</bpmndi:BPMNShape>", label + "</bpmndi:BPMNShape>"))


def _di_edge(f: Flow) -> str:
    wps = "".join(f'<di:waypoint x="{x}" y="{y}" />' for x, y in f.waypoints)
    label = ""
    if f.label:
        mx, my = f.waypoints[len(f.waypoints) // 2]
        label = (f'<bpmndi:BPMNLabel><dc:Bounds x="{mx + 5}" y="{my - 20}" '
                 f'width="{max(20, 7 * len(f.label))}" height="14" /></bpmndi:BPMNLabel>')
    return (f'<bpmndi:BPMNEdge id="{f.bid}_di" bpmnElement="{f.bid}">'
            f"{wps}{label}</bpmndi:BPMNEdge>")


# --- envelopes -------------------------------------------------------------

def process_export(proc: Process, seed: int = 0,
                   overrides: Optional[Dict[str, Any]] = None,
                   profile: str = DEFAULT_PROFILE) -> Dict[str, Any]:
    ov = {"GraphJson": GRAPH_JSON_PROCESS_FORM}
    ov.update(overrides or {})
    r = emit(proc, seed=seed, overrides=ov, profile=profile)
    p = r["process"]
    # Present in the tenant's own ProcessExport, absent from all 77 corpus
    # templates. A generated file without it imported, so it is optional; it
    # is emitted here to match real output on this path.
    p.setdefault("PreserveReferencesAtCheckpoint", False)
    return {
        "Processes": [p],
        "LinkedTasks": {p["UniqueIdentifier"]: r["linked_tasks"]},
        "LinkedSubProcess": {},
        "Version": EXPORT_VERSION,
    }


def template_export(proc: Process, seed: int = 0,
                    template_description: str = "",
                    overrides: Optional[Dict[str, Any]] = None,
                    profile: str = DEFAULT_PROFILE) -> Dict[str, Any]:
    r = emit(proc, seed=seed, overrides=overrides, profile=profile)
    p = r["process"]
    p["UsedTasksJson"] = json.dumps(
        [_upper_guid(u) for u in json.loads(p["UsedTasksJson"])],
        separators=(",", ":"))
    inner = {"Process": p,
             "LinkedTasks": {p["UniqueIdentifier"]: r["linked_tasks"]},
             "LinkedSubProcess": {},
             "Version": EXPORT_VERSION}
    return {"ProcessTemplates": [{
        "Name": proc.name,
        "Modified": p["Modified"],
        "Modifier": p["Modifier"],
        "Tags": [],
        "TemplateProcessTags": [],
        "Description": template_description or proc.description,
        "Version": 1,
        "UniqueIdentifier": str(uuid.uuid4()),
        # Templates keep the variables on the outer wrapper; the inner
        # ProcessVariablesJson is null in all 77 corpus files.
        "ProcessVariablesJson": (json.dumps(r["process_variables"],
                                            separators=(",", ":"), ensure_ascii=False)
                                 if r["process_variables"] else None),
        "ProcessInfo": {**inner, "Process": {**p, "ProcessVariablesJson": None}},
    }]}
