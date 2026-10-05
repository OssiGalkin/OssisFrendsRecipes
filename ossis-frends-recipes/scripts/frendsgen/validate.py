"""Validator.

Every rule here is calibrated against untouched corpus files: anything it
reports on a file Frends itself produced is a bug in the rule, not in the
file. Rules that Frends' own output violates are documented in the README as
deliberately not implemented rather than downgraded silently.
"""

import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Any, Dict, List, Optional

from .shapes import TYPE_TAG, EP_KEYS, ARTIFACT_TYPES
from .ir import VALID_MODES

ERROR, WARN = "ERROR", "WARN"

# BPMN tags that never carry an ElementParameters entry.
NO_PARAMS_TAGS = {
    "definitions", "process", "BPMNDiagram", "BPMNPlane", "BPMNShape",
    "BPMNEdge", "BPMNLabel", "Bounds", "waypoint", "textAnnotation", "text",
    "association", "dataObject", "dataInputAssociation", "dataOutputAssociation",
    "property", "sourceRef", "targetRef", "incoming", "outgoing",
    "signalEventDefinition", "standardLoopCharacteristics",
    "multiInstanceLoopCharacteristics", "extensionElements", "documentation",
    "boundaryEvent", "errorEventDefinition",
    # artifacts with no ElementParameters entry
    "group", "category", "categoryValue", "categoryValueRef",
}
FIXED_SIZE = {0: (36, 36), 1: (100, 80), 2: (50, 50), 5: (36, 36), 6: (36, 36),
              13: (36, 36), 15: (50, 50), 20: (100, 80)}
CONTAINER_TYPES = {10: "multiInstanceLoopCharacteristics",
                   11: "standardLoopCharacteristics"}


def _local(tag: str) -> str:
    return tag.split("}")[-1]


class Finding:
    def __init__(self, sev, rule, msg, where=""):
        self.sev, self.rule, self.msg, self.where = sev, rule, msg, where

    def __str__(self):
        w = f" [{self.where}]" if self.where else ""
        return f"{self.sev} {self.rule}: {self.msg}{w}"


def validate_process(proc: Dict[str, Any]) -> List[Finding]:
    out: List[Finding] = []

    def add(sev, rule, msg, where=""):
        out.append(Finding(sev, rule, msg, where))

    try:
        eps = json.loads(proc.get("ElementParameters") or "[]")
    except Exception as exc:
        add(ERROR, "V000", f"ElementParameters is not JSON: {exc}")
        return out
    try:
        root = ET.fromstring(proc["Bpmn"])
    except Exception as exc:
        add(ERROR, "V000", f"Bpmn is not XML: {exc}")
        return out

    # --- index -------------------------------------------------------------
    by_id: Dict[str, Dict] = {}
    for e in eps:
        if tuple(e.keys()) != EP_KEYS:
            add(ERROR, "V001",
                f"ElementParameters entry has keys {tuple(e.keys())}, "
                f"expected {EP_KEYS}", e.get("Id", "?"))
        if e["Id"] in by_id:
            add(ERROR, "V018", "duplicate ElementParameters Id", e["Id"])
        by_id[e["Id"]] = e

    elems: Dict[str, ET.Element] = {}
    parent_of: Dict[str, Optional[str]] = {}
    dup = set()

    def index(el, parent_id):
        for c in el:
            tag = _local(c.tag)
            cid = c.get("id")
            if cid and tag not in ("BPMNShape", "BPMNEdge", "BPMNDiagram",
                                   "BPMNPlane", "BPMNLabel"):
                if cid in elems:
                    dup.add(cid)
                elems[cid] = c
                parent_of[cid] = parent_id
                index(c, cid if tag == "subProcess" else parent_id)
            else:
                index(c, parent_id)

    proc_el = next((c for c in root if _local(c.tag) == "process"), None)
    if proc_el is None:
        add(ERROR, "V000", "no bpmn2:process element")
        return out
    index(proc_el, None)
    for d in dup:
        add(ERROR, "V018", "duplicate BPMN element id", d)

    # --- id agreement ------------------------------------------------------
    for eid, e in by_id.items():
        if eid in elems:
            continue
        # Type 19 / FrendsTestElementId is the editor's "test this shape"
        # scratch entry. 33 corpus files carry one; it has no diagram element.
        if e["Type"] == 19 and eid == "FrendsTestElementId":
            continue
        add(ERROR, "V002", "ElementParameters entry has no BPMN element", eid)
    for eid, el in elems.items():
        tag = _local(el.tag)
        if tag in NO_PARAMS_TAGS:
            continue
        if eid not in by_id:
            # A sequence flow gets an entry iff its source is a decision
            # gateway: 575/575 gateway flows have one in the corpus, 697/697
            # other flows do not.
            if tag == "sequenceFlow":
                continue
            add(ERROR, "V003", f"BPMN <{tag}> has no ElementParameters entry", eid)
            continue
        t = by_id[eid]["Type"]
        if TYPE_TAG.get(t) != tag:
            add(ERROR, "V004",
                f"Type {t} maps to <{TYPE_TAG.get(t)}> but element is <{tag}>", eid)

    # --- flows -------------------------------------------------------------
    flows = {i: e for i, e in elems.items() if _local(e.tag) == "sequenceFlow"}
    outgoing, incoming = defaultdict(list), defaultdict(list)
    for fid, fe in flows.items():
        s, t = fe.get("sourceRef"), fe.get("targetRef")
        for ref, which in ((s, "sourceRef"), (t, "targetRef")):
            if ref not in elems:
                add(ERROR, "V005", f"{which} {ref!r} does not resolve", fid)
        outgoing[s].append(fid)
        incoming[t].append(fid)

    for eid, el in elems.items():
        if _local(el.tag) == "sequenceFlow":
            continue
        decl_in = [c.text for c in el if _local(c.tag) == "incoming"]
        decl_out = [c.text for c in el if _local(c.tag) == "outgoing"]
        if sorted(decl_in) != sorted(incoming.get(eid, [])):
            add(ERROR, "V006", f"<incoming> {sorted(decl_in)} != actual "
                               f"{sorted(incoming.get(eid, []))}", eid)
        if sorted(decl_out) != sorted(outgoing.get(eid, [])):
            add(ERROR, "V006", f"<outgoing> {sorted(decl_out)} != actual "
                               f"{sorted(outgoing.get(eid, []))}", eid)

    # --- gateways ----------------------------------------------------------
    for eid, el in elems.items():
        if _local(el.tag) != "exclusiveGateway":
            continue
        outs = outgoing.get(eid, [])
        dflt = el.get("default")
        if dflt is None:
            add(ERROR, "V007", "exclusiveGateway has no default flow", eid)
        elif dflt not in outs:
            add(ERROR, "V007", f"default={dflt} is not an outgoing flow", eid)
        for f in outs:
            if f not in by_id:
                add(ERROR, "V007", f"flow {f} leaves a gateway but has no "
                                   f"ElementParameters entry", eid)
        marked = [f for f in outs if by_id.get(f, {}).get("IsDefault")]
        if len(marked) != 1:
            add(ERROR, "V007",
                f"expected exactly one outgoing flow with IsDefault=true, got "
                f"{len(marked)}", eid)
        elif dflt and marked[0] != dflt:
            add(ERROR, "V007",
                f"default attribute is {dflt} but IsDefault is set on {marked[0]}", eid)

    # --- containers --------------------------------------------------------
    for eid, el in elems.items():
        if _local(el.tag) != "subProcess":
            continue
        t = by_id.get(eid, {}).get("Type")
        want = CONTAINER_TYPES.get(t)
        have = [_local(c.tag) for c in el if "LoopCharacteristics" in _local(c.tag)]
        if want and have != [want]:
            add(ERROR, "V008", f"Type {t} container should carry <{want}>, has {have}", eid)
        starts = [c.get("id") for c in el if _local(c.tag) == "startEvent"]
        if len(starts) != 1:
            add(ERROR, "V008", f"container has {len(starts)} inner startEvent(s), "
                               f"expected 1", eid)
        elif by_id.get(starts[0], {}).get("Type") != 13:
            add(ERROR, "V008", "inner startEvent is not Type 13", starts[0])
        if not [c for c in el if _local(c.tag) == "endEvent"]:
            add(ERROR, "V008", "container has no endEvent (Return)", eid)

    # --- retry marker ------------------------------------------------------
    for eid, el in elems.items():
        if _local(el.tag) != "task":
            continue
        marker = any(_local(c.tag) == "standardLoopCharacteristics" for c in el)
        retry = bool(by_id.get(eid, {}).get("ShouldRetry"))
        if marker != retry:
            add(ERROR, "V012",
                f"standardLoopCharacteristics={marker} but ShouldRetry={retry}", eid)

    # --- DI ----------------------------------------------------------------
    di_shapes, di_edges = {}, {}
    for el in root.iter():
        tag = _local(el.tag)
        if tag == "BPMNShape":
            di_shapes[el.get("bpmnElement")] = el
        elif tag == "BPMNEdge":
            di_edges[el.get("bpmnElement")] = el

    for eid, el in elems.items():
        tag = _local(el.tag)
        if tag in NO_PARAMS_TAGS and tag not in ("textAnnotation", "association",
                                                 "dataInputAssociation",
                                                 "dataOutputAssociation"):
            continue
        if tag in ("sequenceFlow", "association", "dataInputAssociation",
                   "dataOutputAssociation"):
            e = di_edges.get(eid)
            if e is None:
                add(ERROR, "V009", f"<{tag}> has no BPMNEdge", eid)
            elif len([c for c in e if _local(c.tag) == "waypoint"]) < 2:
                add(ERROR, "V009", "BPMNEdge has fewer than 2 waypoints", eid)
            continue
        s = di_shapes.get(eid)
        if s is None:
            add(ERROR, "V009", f"<{tag}> has no BPMNShape", eid)
            continue
        b = next((c for c in s if _local(c.tag) == "Bounds"), None)
        if b is None:
            add(ERROR, "V009", "BPMNShape has no dc:Bounds", eid)
            continue
        t = by_id.get(eid, {}).get("Type")
        w, h = float(b.get("width")), float(b.get("height"))
        if t in FIXED_SIZE and (w, h) != FIXED_SIZE[t]:
            add(WARN, "V010", f"Type {t} is {w}x{h}, corpus always has "
                              f"{FIXED_SIZE[t][0]}x{FIXED_SIZE[t][1]}", eid)
        if t == 12 and (w, h) not in ((30.0, 30.0), (100.0, 80.0)):
            add(WARN, "V010", f"scriptTask is {w}x{h}; corpus has 30x30 "
                              f"(Assign Variable) or 100x80 (Code Task)", eid)
        if t in CONTAINER_TYPES:
            if s.get("isExpanded") != "true":
                add(WARN, "V009", "container BPMNShape lacks isExpanded", eid)
        if t == 2 and s.get("isMarkerVisible") != "true":
            add(WARN, "V009", "exclusiveGateway BPMNShape lacks isMarkerVisible", eid)

    # --- containment -------------------------------------------------------
    def bounds(eid):
        s = di_shapes.get(eid)
        if s is None:
            return None
        b = next((c for c in s if _local(c.tag) == "Bounds"), None)
        if b is None:
            return None
        x, y = float(b.get("x")), float(b.get("y"))
        return x, y, x + float(b.get("width")), y + float(b.get("height"))

    for eid, pid in parent_of.items():
        if pid is None or _local(elems[eid].tag) == "sequenceFlow":
            continue
        cb, pb = bounds(eid), bounds(pid)
        if cb and pb and not (cb[0] >= pb[0] and cb[1] >= pb[1]
                              and cb[2] <= pb[2] and cb[3] <= pb[3]):
            add(WARN, "V011", f"shape sits outside its container {pid}", eid)

    # --- parameter cells ---------------------------------------------------
    def walk(o, path, eid):
        if isinstance(o, dict):
            if set(o) == {"mode", "value"}:
                if o["mode"] not in VALID_MODES:
                    add(WARN, "V013", f"{path}: unknown field mode {o['mode']!r}", eid)
            else:
                for k, v in o.items():
                    walk(v, f"{path}.{k}", eid)
        elif isinstance(o, list):
            for it in o:
                walk(it, path + "[]", eid)

    for e in eps:
        walk(e.get("Parameters") or {}, "", e["Id"])

    # --- name placement ----------------------------------------------------
    for eid, el in elems.items():
        e = by_id.get(eid)
        if not e:
            continue
        if e["Type"] in (5, 6):
            if e["Name"] is not None:
                add(WARN, "V015", f"Type {e['Type']} carries an "
                                  f"ElementParameters Name; the corpus keeps event "
                                  f"names on the BPMN element only", eid)
        elif e["Type"] not in (13, 15) and (el.get("name") or e["Name"]):
            if el.get("name") != e["Name"]:
                add(WARN, "V015", f"BPMN name {el.get('name')!r} != "
                                  f"ElementParameters Name {e['Name']!r}", eid)

    # --- named #result references -----------------------------------------
    names = {e["Name"] for e in eps
             if e.get("Name") and e["Type"] not in {4, 16} | ARTIFACT_TYPES}
    for e in eps:
        blob = json.dumps(e.get("Parameters") or {}, ensure_ascii=False)
        for ref in set(re.findall(r"#result\[([^\]]+)\]", blob)):
            if ref not in names:
                add(ERROR, "V014", f"#result[{ref}] does not name any shape", e["Id"])

    # --- envelope ----------------------------------------------------------
    if proc.get("Modifier") is None:
        add(ERROR, "V019",
            "Modifier is null; the Process import rejects it with "
            "\"Value cannot be null. (Parameter 'modifier')\"")
    try:
        triggers = json.loads(proc.get("TriggersJson") or "[]")
    except Exception:
        triggers = []
        add(ERROR, "V017", "TriggersJson is not JSON")
    for tr in triggers:
        if tr.get("id") not in by_id:
            add(ERROR, "V017", f"trigger id {tr.get('id')!r} is not a shape")
        elif by_id[tr["id"]]["Type"] != 0:
            add(ERROR, "V017", f"trigger id {tr['id']!r} is not a Type 0 shape")
    starts = [e for e in eps if e["Type"] == 0]
    if not starts:
        add(ERROR, "V017", "no Type 0 trigger shape")
    if len(starts) != len(triggers):
        add(ERROR, "V017", f"{len(starts)} trigger shape(s) but {len(triggers)} "
                           f"entries in TriggersJson")
    return out


def processes_in(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Accept a ProcessExport or a Template file."""
    if "ProcessTemplates" in doc:
        return [t["ProcessInfo"]["Process"] for t in doc["ProcessTemplates"]]
    return doc.get("Processes", [])


def validate_file(path: str) -> List[Finding]:
    doc = json.load(open(path, encoding="utf-8-sig"))
    out = []
    for p in processes_in(doc):
        out.extend(validate_process(p))
    return out
