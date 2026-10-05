"""IR -> spec document. The inverse of spec.load_spec.

Useful on its own (turn a real export into an editable spec) and as a test:
`load_spec(despec(ir))` must give back an equivalent IR, so the spec format
is provably able to express everything the IR holds.
"""

from typing import Any, Dict, List

from .ir import Process, Node, Val, CONTAINER_KINDS
from .tasks import PARSERS


def _val(v: Val) -> Any:
    return {v.mode: v.value}


def _named(d: Dict[str, Any], n: Node) -> Dict[str, Any]:
    if n.name:
        d["name"] = n.name
    if n.description:
        d["description"] = n.description
    if n.should_not_log_result is not None:
        d["no_log"] = n.should_not_log_result
    return d


def _step(n: Node) -> Dict[str, Any]:
    if n.kind == "task":
        d: Dict[str, Any] = {"task": {"type": n.task, "params": n.params}}
        if n.should_retry:
            d["retry"] = n.max_retry_count
        return _named(d, n)

    if n.kind == "assign":
        body = {"variable": n.variable, "expression": _val(n.expression)}
        if n.return_type is not None:
            body["return_type"] = n.return_type
        d = {"assign": body}
        # the loader defaults the name to "Assign <variable>"; only carry it
        # when it differs, to keep the spec readable
        if n.name and n.name != f"Assign {n.variable}":
            d["name"] = n.name
        if n.description:
            d["description"] = n.description
        return d

    if n.kind == "code":
        body = {"expression": _val(n.expression),
                "statement_mode": n.statement_mode}
        if n.variable:
            body["variable"] = n.variable
        if n.return_type is not None:
            body["return_type"] = n.return_type
        return _named({"code": body}, n)

    if n.kind == "return":
        return _named({"return": _val(n.expression)}, n)

    if n.kind == "throw":
        body = {"message": _val(n.expression)}
        if not n.bypass_global_exception_handler:
            body["bypass_global_exception_handler"] = False
        return _named({"throw": body}, n)

    if n.kind == "decision":
        body: Dict[str, Any] = {}
        if n.name:
            body["name"] = n.name
        body["condition"] = _val(n.condition)
        if n.then:
            body["then"] = [_step(c) for c in n.then]
        if n.otherwise:
            body["else"] = [_step(c) for c in n.otherwise]
        if n.yes_label != "yes":
            body["yes_label"] = n.yes_label
        if n.no_label != "no":
            body["no_label"] = n.no_label
        return {"decision": body}

    if n.kind == "foreach":
        body = {}
        if n.name:
            body["name"] = n.name
        body.update({"item": n.item, "in": _val(n.collection),
                     "do": [_step(c) for c in n.body if c.kind != "inner_start"]})
        return {"foreach": body}

    if n.kind == "while":
        body = {}
        if n.name:
            body["name"] = n.name
        body.update({"condition": _val(n.condition),
                     "max_iterations": n.max_iterations,
                     "do": [_step(c) for c in n.body if c.kind != "inner_start"]})
        return {"while": body}

    raise ValueError(f"no spec form for IR kind {n.kind!r}")


def despec(proc: Process) -> Dict[str, Any]:
    doc: Dict[str, Any] = {"name": proc.name}
    if proc.description:
        doc["description"] = proc.description
    doc["modifier"] = proc.modifier
    doc["trigger"] = ("manual" if proc.trigger.name == "Manual"
                      else {"type": "manual", "name": proc.trigger.name})
    if proc.trigger.config:
        doc["trigger"] = {"type": "manual", "name": proc.trigger.name,
                          "config": proc.trigger.config}
    doc["major_version"] = proc.major_version
    doc["minor_version"] = proc.minor_version
    if proc.variables:
        doc["variables"] = []
        for v in proc.variables:
            d = {"name": v.name, "value": v.value}
            if v.is_secret:
                d["secret"] = True
            if v.mode != "text":
                d["mode"] = v.mode
            if v.description:
                d["description"] = v.description
            doc["variables"].append(d)
    doc["steps"] = [_step(n) for n in proc.body]
    return doc


def to_yaml(doc: Dict[str, Any]) -> str:
    import yaml

    class _D(yaml.SafeDumper):
        pass

    def _str(dumper, data):
        style = "|" if "\n" in data else None
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)

    _D.add_representer(str, _str)
    _D.ignore_aliases = lambda *a: True
    return yaml.dump(doc, Dumper=_D, sort_keys=False, allow_unicode=True,
                     default_flow_style=False, width=100)
