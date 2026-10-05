"""Spec loader.

Rejects anything the IR cannot express, by name, at load time. It never
approximates: an unsupported shape is an error, not a substitution.
"""

import json
from typing import Any, Dict, List

from .ir import (Process, Trigger, Task, AssignVariable, CodeTask, Return,
                 Throw, Decision, Foreach, While, ProcessVariable, Val,
                 SpecError, VALID_MODES)
from .tasks import BUILDERS

SUPPORTED_STEPS = ("task", "assign", "code", "decision", "foreach", "while",
                   "return", "throw")

# Shapes and features that exist in Frends but that this tool refuses to
# guess at. Naming them is more useful than a generic error.
KNOWN_UNSUPPORTED = {
    "scope": "Scope + Catch: no boundaryEvent anywhere in the corpus, so the "
             "serialised form of error handling is unverified.",
    "catch": "Scope + Catch: no boundaryEvent anywhere in the corpus.",
    "subprocess": "Call Subprocess: LinkedSubProcess and GUID resolution are "
                  "unexercised by the corpus.",
    "call_subprocess": "Call Subprocess: unexercised by the corpus.",
    "inclusive_decision": "Inclusive Decision: 1 instance in the corpus, not "
                          "enough to fix the branch-expression schema.",
    "shared_state": "Shared State Task: 3 instances in the corpus.",
    "dmn": "DMN Task: absent from the corpus.",
    "ai_connector": "AI Connector: absent from the corpus.",
    "checkpoint": "Checkpoint: absent from the corpus.",
    "scheduled_resume": "Scheduled Resume: absent from the corpus.",
    "signal_resume": "Signal Resume: absent from the corpus.",
    "intermediate_return": "Intermediate Return: Type 6 without a "
                           "signalEventDefinition is unobserved.",
    "annotation": "Text annotations, groups, associations and data objects "
                  "carry no runtime behaviour and are not generated.",
    "group": "Artifacts are not generated.",
}


def _val(raw: Any, default_mode: str, where: str) -> Val:
    if raw is None:
        raise SpecError(f"{where}: missing expression")
    if isinstance(raw, str):
        return Val(default_mode, raw)
    if isinstance(raw, dict):
        if set(raw) == {"mode", "value"}:
            return Val(raw["mode"], raw["value"])
        if len(raw) == 1:
            (m, v), = raw.items()
            if m in VALID_MODES:
                return Val(m, v)
        raise SpecError(f"{where}: expression must be a string, {{mode, value}} "
                        f"or {{<mode>: value}}; got {sorted(raw)}")
    raise SpecError(f"{where}: expression must be a string or mapping")


def _steps(raw: Any, where: str) -> List:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise SpecError(f"{where}: expected a list of steps")
    return [_step(s, f"{where}[{i}]") for i, s in enumerate(raw)]


def _step(s: Any, where: str):
    if not isinstance(s, dict):
        raise SpecError(f"{where}: each step must be a mapping")
    keys = set(s)
    for bad, why in KNOWN_UNSUPPORTED.items():
        if bad in keys:
            raise SpecError(f"{where}: '{bad}' is not supported. {why}")
    kind = next((k for k in SUPPORTED_STEPS if k in keys), None)
    if kind is None:
        raise SpecError(f"{where}: no supported step key found in {sorted(keys)}. "
                        f"Supported: {list(SUPPORTED_STEPS)}")

    common = dict(name=s.get("name"), description=s.get("description"),
                  should_not_log_result=s.get("no_log"))

    if kind == "task":
        body = s["task"]
        if isinstance(body, str):
            body = {"type": body}
        ttype = body.get("type")
        if ttype not in BUILDERS:
            raise SpecError(f"{where}: unsupported task {ttype!r}. Supported: "
                            f"{sorted(BUILDERS)}. Adding one needs a parameter "
                            f"schema checked against real exports of that task.")
        retry = s.get("retry")
        if retry and not (1 <= int(retry) <= 10):
            raise SpecError(f"{where}: retry must be 1-10 (Frends caps retries "
                            f"at 10), got {retry}")
        return Task(task=ttype, params=body.get("params", s.get("params", {})),
                    should_retry=bool(retry),
                    max_retry_count=int(retry) if retry else None, **common)

    if kind == "assign":
        body = s["assign"]
        if isinstance(body, str):
            body = {"variable": body, "expression": s.get("expression")}
        return AssignVariable(variable=body["variable"],
                              expression=_val(body.get("expression"), "csharp", where),
                              return_type=body.get("return_type"),
                              **{**common, "name": common["name"]
                                 or f"Assign {body['variable']}"})

    if kind == "code":
        body = s["code"]
        if isinstance(body, str):
            body = {"expression": body}
        return CodeTask(expression=_val(body.get("expression"), "csharp", where),
                        statement_mode=bool(body.get("statement_mode", True)),
                        variable=body.get("variable"),
                        return_type=body.get("return_type"), **common)

    if kind == "return":
        body = s["return"]
        if isinstance(body, (str, dict)) and not (
                isinstance(body, dict) and "expression" in body):
            expr = body
        else:
            expr = body.get("expression")
        return Return(expression=_val(expr, "csharp", where), **common)

    if kind == "throw":
        body = s["throw"]
        if isinstance(body, str):
            body = {"message": body}
        return Throw(expression=_val(body.get("message"), "text", where),
                     bypass_global_exception_handler=bool(
                         body.get("bypass_global_exception_handler", True)), **common)

    if kind == "decision":
        body = s["decision"]
        unknown = set(body) - {"name", "condition", "then", "else", "yes_label",
                               "no_label", "description"}
        if unknown:
            raise SpecError(f"{where}: unknown decision key(s) {sorted(unknown)}")
        return Decision(condition=_val(body.get("condition"), "csharp", where),
                        then=_steps(body.get("then"), f"{where}.then"),
                        otherwise=_steps(body.get("else"), f"{where}.else"),
                        yes_label=body.get("yes_label", "yes"),
                        no_label=body.get("no_label", "no"),
                        name=body.get("name") or common["name"],
                        description=body.get("description"))

    if kind == "foreach":
        body = s["foreach"]
        unknown = set(body) - {"name", "item", "in", "do", "description"}
        if unknown:
            raise SpecError(f"{where}: unknown foreach key(s) {sorted(unknown)}")
        return Foreach(item=body.get("item", "item"),
                       collection=_val(body.get("in"), "csharp", where),
                       body=_steps(body.get("do"), f"{where}.do"),
                       name=body.get("name") or common["name"],
                       description=body.get("description"))

    if kind == "while":
        body = s["while"]
        unknown = set(body) - {"name", "condition", "max_iterations", "do",
                               "description"}
        if unknown:
            raise SpecError(f"{where}: unknown while key(s) {sorted(unknown)}")
        return While(condition=_val(body.get("condition"), "csharp", where),
                     max_iterations=int(body.get("max_iterations", 10000)),
                     body=_steps(body.get("do"), f"{where}.do"),
                     name=body.get("name") or common["name"],
                     description=body.get("description"))

    raise SpecError(f"{where}: unhandled step kind {kind}")


def load_spec(doc: Dict[str, Any]) -> Process:
    unknown = set(doc) - {"name", "description", "trigger", "variables", "steps",
                          "modifier", "unique_identifier", "major_version",
                          "minor_version"}
    if unknown:
        raise SpecError(f"unknown top-level key(s) {sorted(unknown)}")
    if not doc.get("name"):
        raise SpecError("spec needs a 'name'")

    trig = doc.get("trigger", "manual")
    if isinstance(trig, str):
        trig = {"type": trig}
    ttype = trig.get("type", "manual")
    if ttype != "manual":
        raise SpecError(
            f"trigger {ttype!r} is not supported. Only the Manual Trigger is: "
            f"Schedule, HTTP, API, File and the rest each have their own config "
            f"schema, and an API trigger additionally binds to an API Management "
            f"endpoint that must already exist in the target tenant.")

    variables = []
    for v in doc.get("variables", []) or []:
        unknown = set(v) - {"name", "value", "secret", "mode", "description"}
        if unknown:
            raise SpecError(f"variable {v.get('name')!r}: unknown key(s) {sorted(unknown)}")
        variables.append(ProcessVariable(
            name=v["name"], value=v.get("value", '""'),
            is_secret=bool(v.get("secret", False)), mode=v.get("mode", "text"),
            description=v.get("description", "")))

    return Process(
        name=doc["name"],
        description=doc.get("description", ""),
        modifier=doc.get("modifier", "frendsgen"),
        unique_identifier=doc.get("unique_identifier"),
        major_version=int(doc.get("major_version", 1)),
        minor_version=int(doc.get("minor_version", 0)),
        trigger=Trigger(name=trig.get("name", "Manual"),
                        trigger_type="ManualTrigger",
                        config=trig.get("config", {})),
        variables=variables,
        body=_steps(doc.get("steps"), "steps"),
    )


def load_file(path: str) -> Process:
    text = open(path, encoding="utf-8-sig").read()
    if path.endswith((".yaml", ".yml")):
        import yaml
        doc = yaml.safe_load(text)
    else:
        doc = json.loads(text)
    return load_spec(doc)
