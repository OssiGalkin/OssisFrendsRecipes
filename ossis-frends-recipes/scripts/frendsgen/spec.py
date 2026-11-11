"""Spec loader.

Rejects anything the IR cannot express, by name, at load time. It never
approximates: an unsupported shape is an error, not a substitution.
"""

import json
import re
from typing import Any, Dict, List

from .ir import (Process, Trigger, Task, AssignVariable, CodeTask, Return,
                 Throw, Decision, Foreach, While, ProcessVariable, Val,
                 SpecError, VALID_MODES, Scope, Catch, IntermediateReturn,
                 CallSubprocess, InclusiveDecision, Branch, SharedState, Dmn,
                 DmnTable, AiConnector, Checkpoint, SignalResume,
                 ScheduledResume, WaitGate, SubprocessRef, UnhandledErrorCall)
from .tasks import BUILDERS
from .triggers import trigger_config, manual_parameter
from .dmn import check_table

SUPPORTED_STEPS = ("task", "assign", "code", "decision", "foreach", "while",
                   "return", "throw", "scope", "call", "inclusive",
                   "shared_state", "dmn", "ai_connector", "checkpoint",
                   "signal_resume", "wait_until")

# Keys allowed beside the step key on any step.
COMMON_KEYS = {"name", "description", "no_log", "retry", "params", "expression",
               "on_error", "respond_early"}

# The target being loaded. Legacy specs name an unnamed Assign Variable
# "Assign <variable>" (unchanged behaviour); the 6.3.2 editor leaves it unnamed.
_TARGET = ["legacy"]

# Shared State operations whose parameter set has been observed.
SHARED_STATE_OPS = {"AddOrUpdate"}

# Shapes and features that exist in Frends but that this tool refuses to
# guess at. Naming them is more useful than a generic error.
KNOWN_UNSUPPORTED = {
    "catch": "A Catch is not a step: put `on_error: {do: <one step>}` on the "
             "Task, Scope or Call Subprocess it guards.",
    "intermediate_return": "An Intermediate Return is not a step: put "
                           "`respond_early: <expression>` on the activity.",
    "scheduled_resume": "A Scheduled Resume only occurs in the Checkpoint loop: "
                        "use `wait_until`.",
    "parallel_foreach": "Frends has no parallel Foreach. ParallelForeach is an "
                        "enum member the editor does not offer.",
    "annotation": "Text annotations, groups and data references carry no runtime "
                  "behaviour and are not generated in an importable Process.",
    "group": "Artifacts are not generated in an importable Process.",
}


# A lambda passed straight to a method on a #var / #result / #trigger value.
# Those values are dynamic, and C# cannot bind a lambda in a dynamically
# dispatched call: Frends 6.3.2 failed an import with CS1977 on
# `#var.jokes.Any(x => ...)`. `((JArray)#var.jokes).Any(x => ...)` is fine.
_DYNAMIC_LAMBDA = re.compile(
    r"#(?:var|result|trigger|process)(?:\.[A-Za-z_]\w*|\[[^\]]*\])*"
    r"\.[A-Za-z_]\w*\(\s*(?:\([^()]*\)|[A-Za-z_]\w*)\s*=>")


def _check_csharp(v: Val, where: str) -> Val:
    if v.mode == "csharp" and isinstance(v.value, str):
        m = _DYNAMIC_LAMBDA.search(v.value)
        if m:
            raise SpecError(
                f"{where}: {m.group(0)!r} passes a lambda to a method on a dynamic "
                f"value (CS1977 on import). Cast the value to its static type "
                f"first, e.g. ((JArray)#var.list).Any(x => ...).")
    return v


def _val(raw: Any, default_mode: str, where: str) -> Val:
    if raw is None:
        raise SpecError(f"{where}: missing expression")
    if isinstance(raw, str):
        return _check_csharp(Val(default_mode, raw), where)
    if isinstance(raw, dict):
        if set(raw) == {"mode", "value"}:
            return _check_csharp(Val(raw["mode"], raw["value"]), where)
        if len(raw) == 1:
            (m, v), = raw.items()
            if m in VALID_MODES:
                return _check_csharp(Val(m, v), where)
        raise SpecError(f"{where}: expression must be a string, {{mode, value}} "
                        f"or {{<mode>: value}}; got {sorted(raw)}")
    raise SpecError(f"{where}: expression must be a string or mapping")


def _steps(raw: Any, where: str) -> List:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise SpecError(f"{where}: expected a list of steps")
    out = []
    for i, s in enumerate(raw):
        n = _step(s, f"{where}[{i}]")
        out.extend(n if isinstance(n, list) else [n])
    return out


def _vals(raw: Any, default_mode: str, where: str):
    if not isinstance(raw, dict):
        raise SpecError(f"{where}: expected a mapping of parameter -> expression")
    return {k: _val(v, default_mode, f"{where}.{k}") for k, v in raw.items()}


def _step(s: Any, where: str):
    n = _step_core(s, where)
    head = n[0] if isinstance(n, list) else n
    if isinstance(s, dict) and s.get("on_error") is not None:
        oe = s["on_error"]
        if not isinstance(oe, dict) or "do" not in oe:
            raise SpecError(f"{where}.on_error: expected {{do: <one step>, "
                            f"variable: error}}")
        unknown = set(oe) - {"do", "variable"}
        if unknown:
            raise SpecError(f"{where}.on_error: unknown key(s) {sorted(unknown)}")
        do = oe["do"]
        if isinstance(do, list):
            if len(do) != 1:
                raise SpecError(
                    f"{where}.on_error: the docs allow exactly one shape after a "
                    f"Catch; use a scope step for more")
            do = do[0]
        if isinstance(do, dict):
            bad = [k for k in ("decision", "inclusive", "wait_until") if k in do]
            if bad:
                raise SpecError(
                    f"{where}.on_error: a {bad[0]} cannot be the Catch handler. The "
                    f"docs allow exactly one shape after a Catch and a {bad[0]} "
                    f"expands to several; put it inside a scope step and use the "
                    f"scope as the handler.")
            if do.get("on_error") is not None or do.get("respond_early") is not None:
                raise SpecError(f"{where}.on_error: the handler cannot carry its own "
                                f"on_error or respond_early; use a scope step")
        if isinstance(do, dict) and any(k in do for k in ("throw", "return")):
            raise SpecError(
                f"{where}.on_error: a Catch handler cannot end the Process. Frends "
                f"refuses the import: a Catch must rejoin at the shape its guarded "
                f"shape reaches on success. Record the error in a pre-initialised "
                f"Process Variable in the handler, then Throw after the rejoin.")
        handler = _step(do, f"{where}.on_error.do")
        head.catch = Catch(variable=oe.get("variable", "error"), handler=handler)
    if isinstance(s, dict) and s.get("respond_early") is not None:
        r = s["respond_early"]
        if isinstance(r, dict) and "expression" in r:
            r = r["expression"]
        head.respond_early = IntermediateReturn(
            expression=_val(r, "csharp", f"{where}.respond_early"))
    return n


def _step_core(s: Any, where: str):
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
    extra = keys - COMMON_KEYS - {kind}
    if extra:
        raise SpecError(f"{where}: unknown key(s) {sorted(extra)} beside {kind!r}")

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
        var = body.get("variable") or ""
        _check_name(var, where)
        return AssignVariable(variable=var,
                              expression=_val(body.get("expression"), "csharp", where),
                              return_type=body.get("return_type"),
                              assigns=bool(var),
                              **{**common, "name": common["name"] if "name" in s
                                 else (f"Assign {var}" if var and _TARGET[0] == "legacy"
                                       else None)})

    if kind == "code":
        body = s["code"]
        if isinstance(body, str):
            body = {"expression": body}
        stmt = bool(body.get("statement_mode", True))
        expr = _val(body.get("expression"), "csharp", where)
        _check_code_returns(stmt, body.get("variable"), str(expr.value), where)
        _check_name(body.get("variable"), where)
        return CodeTask(expression=expr,
                        statement_mode=stmt,
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
        _check_name(body.get("item"), where)
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

    if kind == "scope":
        body = s["scope"] or {}
        if isinstance(body, list):
            body = {"do": body}
        unknown = set(body) - {"name", "do", "description"}
        if unknown:
            raise SpecError(f"{where}: unknown scope key(s) {sorted(unknown)}")
        return Scope(body=_steps(body.get("do"), f"{where}.do"),
                     name=body.get("name") or common["name"],
                     description=body.get("description") or common["description"])

    if kind == "call":
        body = s["call"]
        if isinstance(body, str):
            body = {"subprocess": body}
        unknown = set(body) - {"subprocess", "params"}
        if unknown:
            raise SpecError(f"{where}: unknown call key(s) {sorted(unknown)}")
        # the editor's default mode for a Subprocess parameter is text
        return CallSubprocess(subprocess=body["subprocess"],
                              params=_vals(body.get("params") or {}, "text",
                                           f"{where}.params"),
                              **{**common, "name": common["name"] or body["subprocess"]})

    if kind == "inclusive":
        body = s["inclusive"]
        unknown = set(body) - {"name", "branches", "default", "description"}
        if unknown:
            raise SpecError(f"{where}: unknown inclusive key(s) {sorted(unknown)}")
        branches = []
        for i, b in enumerate(body.get("branches") or []):
            bw = f"{where}.branches[{i}]"
            if set(b) - {"name", "condition", "do"} or not b.get("name"):
                raise SpecError(f"{bw}: a branch is {{name, condition, do}} and "
                                f"every branch needs a unique name (docs)")
            branches.append(Branch(b["name"], _val(b.get("condition"), "csharp", bw),
                                   _steps(b.get("do"), f"{bw}.do")))
        if not branches:
            raise SpecError(f"{where}: an inclusive decision needs branches")
        names = [b.name for b in branches]
        d = body.get("default") or {}
        dflt = Branch(d.get("name", "Default"), None, _steps(d.get("do"), f"{where}.default.do"))
        if len(set(names + [dflt.name])) != len(names) + 1:
            raise SpecError(f"{where}: branch names must be unique (docs)")
        return InclusiveDecision(branches=branches, default=dflt,
                                 name=body.get("name") or common["name"],
                                 description=body.get("description"))

    if kind == "shared_state":
        body = s["shared_state"]
        unknown = set(body) - {"operation", "key", "value", "ttl", "ttl_multiplier",
                               "throw_if_false", "global"}
        if unknown:
            raise SpecError(f"{where}: unknown shared_state key(s) {sorted(unknown)}")
        op = body.get("operation", "AddOrUpdate")
        if op not in SHARED_STATE_OPS:
            raise SpecError(f"{where}: Shared State {op!r} is not supported: only "
                            f"{sorted(SHARED_STATE_OPS)} has an observed parameter set")
        return SharedState(operation=op, key=_val(body.get("key"), "text", where),
                           value=_val(body.get("value", "null"), "csharp", where),
                           ttl_value=str(body.get("ttl", 1)),
                           ttl_multiplier=int(body.get("ttl_multiplier", 60)),
                           throw_if_false=bool(body.get("throw_if_false", True)),
                           global_scope=bool(body.get("global", False)), **common)

    if kind == "dmn":
        body = s["dmn"]
        unknown = set(body) - {"inputs", "output", "rules", "xml", "parameters"}
        if unknown:
            raise SpecError(f"{where}: unknown dmn key(s) {sorted(unknown)}")
        if "xml" in body:
            t = DmnTable(raw_xml=body["xml"], raw_parameters=body.get("parameters", "{}"))
        else:
            t = DmnTable(inputs=list(body.get("inputs") or []),
                         output=body.get("output", "Result"),
                         rules=list(body.get("rules") or []))
        check_table(t, where)
        return Dmn(table=t, **common)

    if kind == "ai_connector":
        body = s["ai_connector"] or {}
        unknown = set(body) - {"params", "user_prompt", "model"}
        if unknown:
            raise SpecError(f"{where}: unknown ai_connector key(s) {sorted(unknown)}")
        if not body.get("params"):
            raise SpecError(
                f"{where}: the AI Connector's parameter set is only observed once, "
                f"so it is passed through: give `params` copied from a lifted export "
                f"(`frendsgen lift --spec`), then override user_prompt / model")
        params = json.loads(json.dumps(body["params"]))
        if "user_prompt" in body:
            params["userPrompts"] = [{"mode": "text", "value": body["user_prompt"],
                                      "disableWordWrap": False}]
        if "model" in body:
            params["modelName"] = body["model"]
        return AiConnector(params=params, **common)

    if kind == "checkpoint":
        return _checkpoint(s["checkpoint"] or {}, common, where)

    if kind == "signal_resume":
        body = s["signal_resume"] or {}
        return SignalResume(correlation_id=_val(
            body.get("correlation_id", "#process.executionid"), "csharp", where),
            **common)

    if kind == "wait_until":
        body = s["wait_until"]
        unknown = set(body) - {"checkpoint", "condition", "every_minutes",
                               "max_iterations", "name", "yes_label", "no_label"}
        if unknown:
            raise SpecError(f"{where}: unknown wait_until key(s) {sorted(unknown)}")
        cp = _checkpoint(body.get("checkpoint") or {}, dict(name=None, description=None,
                                                             should_not_log_result=None),
                         where)
        gate = WaitGate(condition=_val(body.get("condition"), "csharp", where),
                        checkpoint=cp,
                        resume=ScheduledResume(
                            max_iterations=int(body.get("max_iterations", 1)),
                            interval_minutes=int(body.get("every_minutes", 60))),
                        yes_label=body.get("yes_label", "yes"),
                        no_label=body.get("no_label", "no"),
                        name=body.get("name"))
        return [cp, gate]

    raise SpecError(f"{where}: unhandled step kind {kind}")


# C# reserved words. A variable named after one cannot be referenced as #var.x
# in generated C# (e.g. `short`), so refuse it up front.
CSHARP_KEYWORDS = set("""abstract as base bool break byte case catch char checked class const
continue decimal default delegate do double else enum event explicit extern false finally
fixed float for foreach goto if implicit in int interface internal is lock long namespace
new null object operator out override params private protected public readonly ref return
sbyte sealed short sizeof stackalloc static string struct switch this throw true try typeof
uint ulong unchecked unsafe ushort using virtual void volatile while""".split())


def _check_name(name, where: str):
    if name and name in CSHARP_KEYWORDS:
        raise SpecError(f"{where}: {name!r} is a C# keyword and cannot be a variable "
                        f"name; pick another (e.g. {name}Value)")


_RETURN_VALUE = re.compile(r"\breturn\s+[^;\s]")


def _check_code_returns(statement_mode: bool, variable, code: str, where: str):
    """A statement-mode Code Task compiles to a delegate. With no variable to
    assign it is void, so `return <value>;` fails with CS8030 (seen on a
    Frends 6.3.2 import). With a variable it must return a value."""
    if not statement_mode:
        return
    if not variable and _RETURN_VALUE.search(code):
        raise SpecError(
            f"{where}: a statement-mode Code Task without `variable` compiles to a "
            f"void delegate, so `return <value>;` is error CS8030. Either set "
            f"`variable:` to keep the value, or drop the returned value.")
    if variable and not re.search(r"\breturn\b", code):
        raise SpecError(
            f"{where}: a statement-mode Code Task with `variable: {variable}` must "
            f"`return` the value to assign.")


def _checkpoint(body, common, where):
    unknown = set(body) - {"name", "correlation_id", "ttl_minutes", "continue_execution"}
    if unknown:
        raise SpecError(f"{where}: unknown checkpoint key(s) {sorted(unknown)}")
    return Checkpoint(
        correlation_id=_val(body.get("correlation_id", "#process.executionid"),
                            "csharp", where),
        ttl_minutes=int(body.get("ttl_minutes", 1440)),
        continue_execution=bool(body.get("continue_execution", False)),
        **{**common, "name": body.get("name") or common.get("name")})


def _trigger(t: Any, where: str) -> Trigger:
    if isinstance(t, str):
        t = {"type": t}
    unknown = set(t) - {"type", "name", "config", "parameters", "no_log_parameters",
                        "subprocess"}
    if unknown:
        raise SpecError(f"{where}: unknown trigger key(s) {sorted(unknown)}")
    kind = t.get("type", "manual")
    ttype, cfg = trigger_config(kind, t.get("config") or {}, where)
    params = [manual_parameter(p, f"{where}.parameters[{i}]")
              for i, p in enumerate(t.get("parameters") or [])]
    if params and ttype != "ManualTrigger":
        raise SpecError(f"{where}: only a Manual Trigger takes parameters")
    if ttype == "ConditionalTrigger":
        if cfg.get("processGuid"):
            raise SpecError(
                f"{where}: the Conditional Trigger's condition Subprocess GUID is "
                f"per-Tenant; name it with `subprocess: <name>` and bind it like any "
                f"other Subprocess, instead of a literal processGuid")
        if not t.get("subprocess"):
            raise SpecError(f"{where}: a Conditional Trigger needs `subprocess: <name>`"
                            f" for its condition Subprocess")
    elif t.get("subprocess"):
        raise SpecError(f"{where}: only a Conditional Trigger takes `subprocess`")
    default_names = {"ManualTrigger": "Manual", "HttpTrigger": "HTTP",
                     "HttpApiTrigger": "API", "FileWatchTrigger": "File",
                     "ScheduleTrigger": "Schedule", "ConditionalTrigger": "Conditional",
                     "McpTrigger": "MCP", "TcpTrigger": "TCP",
                     "AzureEventHubTrigger": "Azure Event Hub",
                     "RabbitMQTrigger": "RabbitMQ", "QueueTrigger": "Queue",
                     "ServiceBusTrigger": "Service Bus"}
    return Trigger(name=t.get("name", default_names[ttype]), trigger_type=ttype,
                   config=cfg, manual_parameters=params,
                   should_not_log_parameters=t.get("no_log_parameters"),
                   condition_subprocess=t.get("subprocess"))


def subprocess_refs_from_export(doc: Dict[str, Any]) -> Dict[str, SubprocessRef]:
    """Bind Subprocesses by name from an export's LinkedSubProcess, the way task
    GUIDs are bound from LinkedTasks, and from any Subprocess the export itself
    contains (IsSubprocess true): its UniqueIdentifier and Manual Trigger
    parameters are exactly what a caller binds to."""
    out = {}
    procs = doc.get("Processes") or [t["ProcessInfo"]["Process"]
                                     for t in doc.get("ProcessTemplates") or []]
    for p in procs:
        if not p.get("IsSubprocess"):
            continue
        # Copied verbatim: a caller's LinkedSubProcess entry mirrors the
        # Subprocess's own ManualTriggerJson. A copy with
        # nonStringifiedDefaultValue stripped was refused on a 6.3.2 import
        # ("can't find subprocess"); the export Frends then wrote for the same
        # caller kept every key.
        mt = p.get("ManualTriggerJson") or "[]"
        params = json.loads(mt)
        out[p["Name"]] = SubprocessRef(name=p["Name"], guid=p["UniqueIdentifier"],
                                       manual_triggers_json=mt,
                                       parameters=[q.get("name") for q in params])
    for lst in (doc.get("LinkedSubProcess") or {}).values():
        for e in lst:
            mt = e.get("ManualTriggersJson") or "[]"
            names = [p.get("name") for p in json.loads(mt)]
            out[e["SubProcessName"]] = SubprocessRef(
                name=e["SubProcessName"], guid=e["SubProcessGuid"],
                manual_triggers_json=mt, parameters=names)
    return out


def load_spec(doc: Dict[str, Any]) -> Process:
    unknown = set(doc) - {"name", "description", "trigger", "triggers", "variables",
                          "steps", "modifier", "unique_identifier", "major_version",
                          "minor_version", "target", "subprocesses",
                          "on_unhandled_error", "preserve_references_at_checkpoint",
                          "subprocess"}
    if unknown:
        raise SpecError(f"unknown top-level key(s) {sorted(unknown)}")
    if not doc.get("name"):
        raise SpecError("spec needs a 'name'")

    _TARGET[0] = str(doc.get("target", "legacy"))
    if "trigger" in doc and "triggers" in doc:
        raise SpecError("give either 'trigger' or 'triggers', not both")
    raw_triggers = doc.get("triggers") or [doc.get("trigger", "manual")]
    triggers = [_trigger(t, f"triggers[{i}]") for i, t in enumerate(raw_triggers)]

    subs = {}
    for i, sp in enumerate(doc.get("subprocesses") or []):
        unknown = set(sp) - {"name", "guid", "parameters", "manual_triggers_json"}
        if unknown or not sp.get("name") or not sp.get("guid"):
            raise SpecError(f"subprocesses[{i}]: expected {{name, guid, parameters"
                            f" | manual_triggers_json}}")
        if "manual_triggers_json" in sp:
            mt = sp["manual_triggers_json"]
            names = [p.get("name") for p in json.loads(mt)]
        else:
            # Synthesised: one text parameter per name, as the editor writes a
            # text parameter. Prefer --subprocesses-from for the real schema.
            names = list(sp.get("parameters") or [])
            mt = json.dumps([manual_parameter({"name": n}, f"subprocesses[{i}]")
                             for n in names], separators=(",", ":"))
        subs[sp["name"]] = SubprocessRef(name=sp["name"], guid=sp["guid"],
                                         manual_triggers_json=mt, parameters=names)

    oue = None
    if doc.get("on_unhandled_error"):
        o = doc["on_unhandled_error"]
        if isinstance(o, str):
            o = {"subprocess": o}
        oue = UnhandledErrorCall(subprocess=o["subprocess"],
                                 params=_vals(o.get("params") or {}, "text",
                                              "on_unhandled_error.params"))

    variables = []
    for v in doc.get("variables", []) or []:
        unknown = set(v) - {"name", "value", "secret", "mode", "description"}
        if unknown:
            raise SpecError(f"variable {v.get('name')!r}: unknown key(s) {sorted(unknown)}")
        _check_name(v.get("name"), f"variable {v.get('name')!r}")
        raw = v.get("value", '""')
        try:
            json.loads(raw)
        except (TypeError, ValueError):
            raise SpecError(
                f"variable {v.get('name')!r}: value {raw!r} is not JSON. A Process "
                f"Variable's value is parsed as a JSON token, not compiled as C#: "
                f"Frends 6.3.2 failed a run with 'Unknown token type new JArray()'. "
                f"Write a quoted JSON string for text, 5 or true for a number or "
                f"boolean. For a list you will add to, use an assign step with "
                f"new JArray(): [] loads as a fixed-size System.Array.")
        variables.append(ProcessVariable(
            name=v["name"], value=raw,
            is_secret=bool(v.get("secret", False)), mode=v.get("mode", "text"),
            description=v.get("description", "")))

    if doc.get("subprocess"):
        if len(triggers) != 1 or triggers[0].trigger_type != "ManualTrigger":
            raise SpecError("a Subprocess has exactly one Trigger, a Manual Trigger "
                            "whose parameters are what callers pass")
    return Process(
        name=doc["name"],
        description=doc.get("description", ""),
        modifier=doc.get("modifier", "frendsgen"),
        unique_identifier=doc.get("unique_identifier"),
        major_version=int(doc.get("major_version", 1)),
        minor_version=int(doc.get("minor_version", 0)),
        trigger=triggers[0],
        extra_triggers=triggers[1:],
        variables=variables,
        body=_steps(doc.get("steps"), "steps"),
        subprocesses=subs,
        on_unhandled_error=oue,
        preserve_references_at_checkpoint=doc.get("preserve_references_at_checkpoint"),
        target=str(doc.get("target", "legacy")),
        is_subprocess=bool(doc.get("subprocess", False)),
    )


def load_file(path: str) -> Process:
    text = open(path, encoding="utf-8-sig").read()
    if path.endswith((".yaml", ".yml")):
        import yaml
        doc = yaml.safe_load(text)
    else:
        doc = json.loads(text)
    return load_spec(doc)
