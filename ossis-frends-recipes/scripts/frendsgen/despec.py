"""IR -> spec document. The inverse of spec.load_spec.

Useful on its own (turn a real export into an editable spec) and as a test:
`load_spec(despec(ir))` must give back an equivalent IR, so the spec format
is provably able to express everything the IR holds.
"""

from typing import Any, Dict, List

from .ir import Process, Node, Val, CONTAINER_KINDS
from .tasks import PARSERS
from .shapes import TRIGGER_TYPES
from .triggers import TEMPLATES


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


def _vals(d):
    return {k: _val(v) for k, v in d.items()}


def _step(n: Node) -> Dict[str, Any]:
    d = _step_core(n)
    if n.catch is not None:
        oe = {"do": _step(n.catch.handler)}
        if n.catch.variable != "error":
            oe["variable"] = n.catch.variable
        d["on_error"] = oe
    if n.respond_early is not None:
        d["respond_early"] = _val(n.respond_early.expression)
    return d


def _steps(seq):
    out = []
    for i, c in enumerate(seq):
        if c.kind == "inner_start":
            continue
        if c.kind == "checkpoint" and i + 1 < len(seq) and seq[i + 1].kind == "wait_gate" \
                and seq[i + 1].checkpoint is c:
            continue                       # folded into the wait_until below
        out.append(_step(c))
    return out


def _cp(c) -> Dict[str, Any]:
    d: Dict[str, Any] = {}
    if c.name:
        d["name"] = c.name
    d["correlation_id"] = _val(c.correlation_id)
    if c.ttl_minutes != 1440:
        d["ttl_minutes"] = c.ttl_minutes
    if c.continue_execution:
        d["continue_execution"] = True
    return d


def _step_core(n: Node) -> Dict[str, Any]:
    if n.kind == "scope":
        body = {}
        if n.name:
            body["name"] = n.name
        if n.description:
            body["description"] = n.description
        body["do"] = _steps(n.body)
        return {"scope": body}

    if n.kind == "call_subprocess":
        d = {"call": {"subprocess": n.subprocess, "params": _vals(n.params)}}
        if n.name and n.name != n.subprocess:
            d["name"] = n.name
        if n.description:
            d["description"] = n.description
        return d

    if n.kind == "inclusive":
        body = {}
        if n.name:
            body["name"] = n.name
        body["branches"] = [{"name": b.name, "condition": _val(b.condition),
                             "do": _steps(b.steps)} for b in n.branches]
        body["default"] = {"name": n.default.name, "do": _steps(n.default.steps)}
        return {"inclusive": body}

    if n.kind == "shared_state":
        return _named({"shared_state": {
            "operation": n.operation, "key": _val(n.key), "value": _val(n.value),
            "ttl": n.ttl_value, "ttl_multiplier": n.ttl_multiplier,
            "throw_if_false": n.throw_if_false, "global": n.global_scope}}, n)

    if n.kind == "dmn":
        t = n.table
        if t.raw_xml is not None:
            body = {"xml": t.raw_xml, "parameters": t.raw_parameters or "{}"}
        else:
            body = {"inputs": t.inputs, "output": t.output, "rules": t.rules}
        return _named({"dmn": body}, n)

    if n.kind == "ai_connector":
        return _named({"ai_connector": {"params": n.params}}, n)

    if n.kind == "checkpoint":
        d = {"checkpoint": _cp(n)}
        if n.description:
            d["description"] = n.description
        if n.should_not_log_result is not None:
            d["no_log"] = n.should_not_log_result
        return d

    if n.kind == "signal_resume":
        return _named({"signal_resume": {"correlation_id": _val(n.correlation_id)}}, n)

    if n.kind == "wait_gate":
        body = {"checkpoint": _cp(n.checkpoint), "condition": _val(n.condition),
                "every_minutes": n.resume.interval_minutes,
                "max_iterations": n.resume.max_iterations}
        if n.name:
            body["name"] = n.name
        if n.yes_label != "yes":
            body["yes_label"] = n.yes_label
        if n.no_label != "no":
            body["no_label"] = n.no_label
        return {"wait_until": body}

    if n.kind == "task":
        d: Dict[str, Any] = {"task": {"type": n.task, "params": n.params}}
        if n.should_retry:
            d["retry"] = n.max_retry_count
        return _named(d, n)

    if n.kind == "assign":
        body = {"variable": n.variable, "expression": _val(n.expression)}
        if not n.assigns:
            body = {"expression": _val(n.expression)}
        if n.return_type is not None:
            body["return_type"] = n.return_type
        d = {"assign": body}
        # the loader defaults the name to "Assign <variable>"; only carry it
        # when it differs, to keep the spec readable
        default = (f"Assign {n.variable}" if n.assigns and _TARGET[0] == "legacy"
                   else None)
        if (n.name or None) != default:
            d["name"] = n.name             # null keeps an unnamed shape unnamed
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
            body["then"] = _steps(n.then)
        if n.otherwise:
            body["else"] = _steps(n.otherwise)
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
                     "do": _steps(n.body)})
        return {"foreach": body}

    if n.kind == "while":
        body = {}
        if n.name:
            body["name"] = n.name
        body.update({"condition": _val(n.condition),
                     "max_iterations": n.max_iterations,
                     "do": _steps(n.body)})
        return {"while": body}

    raise ValueError(f"no spec form for IR kind {n.kind!r}")


_TARGET = ["legacy"]


def despec(proc: Process) -> Dict[str, Any]:
    _TARGET[0] = proc.target
    doc: Dict[str, Any] = {"name": proc.name}
    if proc.description:
        doc["description"] = proc.description
    doc["modifier"] = proc.modifier
    if proc.target != "legacy":
        doc["target"] = proc.target
    if proc.is_subprocess:
        doc["subprocess"] = True
    trigs = []
    for t in proc.triggers:
        kind = next(k for k, v in TRIGGER_TYPES.items() if v == t.trigger_type)
        d: Dict[str, Any] = {"type": kind}
        if t.name:
            d["name"] = t.name
        if t.manual_parameters:
            d["parameters"] = []
            for p in t.manual_parameters:
                q = {"name": p["name"], "default": p.get("defaultValue", "")}
                if p.get("isSecret"):
                    q["secret"] = True
                if p.get("description"):
                    q["description"] = p["description"]
                d["parameters"].append(q)
        else:
            base = TEMPLATES.get(t.trigger_type, {})
            cfg = {k: v for k, v in t.config.items() if base.get(k, object()) != v}
            if cfg:
                d["config"] = cfg
        if t.should_not_log_parameters is not None:
            d["no_log_parameters"] = t.should_not_log_parameters
        if t.condition_subprocess:
            d["subprocess"] = t.condition_subprocess
        trigs.append(d)
    if len(trigs) == 1 and set(trigs[0]) <= {"type", "name"} and \
            trigs[0].get("name", "Manual") == "Manual" and trigs[0]["type"] == "manual":
        doc["trigger"] = "manual"
    elif len(trigs) == 1:
        doc["trigger"] = trigs[0]
    else:
        doc["triggers"] = trigs
    if proc.subprocesses:
        doc["subprocesses"] = [{"name": r.name, "guid": r.guid,
                                "manual_triggers_json": r.manual_triggers_json}
                               for r in proc.subprocesses.values()]
    if proc.on_unhandled_error is not None:
        doc["on_unhandled_error"] = {"subprocess": proc.on_unhandled_error.subprocess,
                                     "params": _vals(proc.on_unhandled_error.params)}
    if proc.preserve_references_at_checkpoint is not None:
        doc["preserve_references_at_checkpoint"] = proc.preserve_references_at_checkpoint
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
    doc["steps"] = _steps(proc.body)
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
