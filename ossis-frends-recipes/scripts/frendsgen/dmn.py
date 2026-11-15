"""DMN Task decision tables.

The serialised form is copied from the one DMN Task in the Frends 6.3.2
reference export (assets/fixtures/shapes-6.3.json): a Camunda-flavoured DMN
1.3 document in `dmnXml`, the decision id `decisionId_<shape id>` in
`decisionId`, and a JSON object in `parameters` that maps each `var.`/`env.`
name the table reads to the `#var.`/`#env.` reference that feeds it.

Rules the docs state and this module enforces: no `#` inside the table
(`var.age`, not `#var.age`); FEEL unary tests in input entries (`<5`,
`[18..65)`); outputs read back as `#result[<DMN Task name>].<output name>`.

One output column and the default hit policy are all the reference export
shows, so that is all this builds. A table lifted from an export is carried
verbatim instead (raw_xml), so nothing in it is lost.
"""

import json
import random
import re
import string
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple

from .ir import DmnTable, SpecError

DMN_NS = "https://www.omg.org/spec/DMN/20191111/MODEL/"
CAMUNDA_NS = "http://camunda.org/schema/1.0/dmn"
_REF = re.compile(r"\b((?:var|env)\.[A-Za-z_][A-Za-z0-9_.]*)")
TYPES = {"string", "integer", "long", "double", "boolean", "date"}


def _x(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _xt(s: str) -> str:
    """Element text: the reference export escapes < and > but not quotes."""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _ids(seed: str):
    rnd = random.Random(seed)

    def new(prefix):
        return prefix + "_" + "".join(rnd.choice(string.digits + string.ascii_lowercase)
                                      for _ in range(7))
    return new


def check_table(t: DmnTable, where: str):
    if t.raw_xml is not None:
        return
    if not t.inputs:
        raise SpecError(f"{where}: a DMN table needs at least one input")
    for i in t.inputs:
        expr = i.get("expression", "")
        if "#" in expr:
            raise SpecError(f"{where}: DMN input {expr!r} uses '#'. Inside a DMN "
                            f"table write var.x / env.Group.Name, never #var.x")
        if i.get("type", "string") not in TYPES:
            raise SpecError(f"{where}: DMN input type {i.get('type')!r}; use one "
                            f"of {sorted(TYPES)}")
    for r in t.rules:
        if len(r.get("when", [])) != len(t.inputs):
            raise SpecError(f"{where}: every rule needs one 'when' entry per input "
                            f"({len(t.inputs)}), got {r.get('when')}")
        for cell in r.get("when", []) + [r.get("then", "")]:
            if "#" in str(cell):
                raise SpecError(f"{where}: DMN cell {cell!r} uses '#'")


def build_dmn(t: DmnTable, shape_id: str) -> Tuple[str, str, str]:
    """-> (dmnXml, decisionId, parameters JSON)"""
    decision_id = f"decisionId_{shape_id}"
    if t.raw_xml is not None:
        # carried verbatim: keep the decision id the XML itself declares
        m = re.search(r'<decision id="([^"]+)"', t.raw_xml)
        return t.raw_xml, (m.group(1) if m else decision_id), t.raw_parameters or "{}"
    new = _ids(shape_id)
    refs: List[str] = []
    for i in t.inputs:
        for m in _REF.findall(i["expression"]):
            if m not in refs:
                refs.append(m)
    o = [f'<definitions xmlns="{DMN_NS}" xmlns:camunda="{CAMUNDA_NS}" '
         f'id="definitions" name="definitions" namespace="{CAMUNDA_NS}">'
         f'<decision id="{decision_id}" name="">']
    for r in refs:
        k = r.replace(".", "")
        o.append(f'<informationRequirement id="ir_{k}"><requiredInput '
                 f'href="#id_{k}"/></informationRequirement>')
    o.append('<decisionTable id="decisionTable">')
    for i in t.inputs:
        o.append(f'<input id="{new("InputClause")}" camunda:inputVariable='
                 f'"{_x(i.get("name", "InputName"))}"><inputExpression '
                 f'id="{new("LiteralExpression")}" typeRef="{_x(i.get("type", "string"))}">'
                 f'<text>{_xt(i["expression"])}</text></inputExpression></input>')
    o.append(f'<output id="result" label="{_x(t.output)}" name="{_x(t.output)}"/>')
    for r in t.rules:
        o.append(f'<rule id="{new("DecisionRule")}">')
        for cell in r["when"]:
            o.append(f'<inputEntry id="{new("UnaryTests")}"><text>{_xt(cell)}</text>'
                     f'</inputEntry>')
        o.append(f'<outputEntry id="{new("LiteralExpression")}"><text>'
                 f'{_xt(r["then"])}</text></outputEntry></rule>')
    o.append("</decisionTable></decision>")
    for r in refs:
        o.append(f'<inputData id="id_{r.replace(".", "")}" name="{r}"/>')
    o.append("</definitions>")
    params = {r: "#" + r for r in refs}
    return "".join(o), decision_id, json.dumps(params, separators=(",", ":"))


def parse_dmn(xml: str, parameters: str) -> DmnTable:
    """Read a table back. Always keeps the original XML verbatim as raw_xml;
    the parsed columns and rules are for reading and editing."""
    t = DmnTable(raw_xml=xml, raw_parameters=parameters)
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return t
    q = lambda tag: f"{{{DMN_NS}}}{tag}"
    table = root.find(f"{q('decision')}/{q('decisionTable')}")
    if table is None:
        return t
    for i in table.findall(q("input")):
        ie = i.find(q("inputExpression"))
        tx = ie.find(q("text")) if ie is not None else None
        t.inputs.append({"name": i.get(f"{{{CAMUNDA_NS}}}inputVariable", "InputName"),
                         "type": ie.get("typeRef", "string") if ie is not None else "string",
                         "expression": (tx.text or "") if tx is not None else ""})
    out = table.find(q("output"))
    if out is not None:
        t.output = out.get("name") or out.get("label") or "Result"
    for r in table.findall(q("rule")):
        when = [(e.find(q("text")).text or "") for e in r.findall(q("inputEntry"))]
        oe = r.find(q("outputEntry"))
        then = (oe.find(q("text")).text or "") if oe is not None else ""
        t.rules.append({"when": when, "then": then})
    return t
