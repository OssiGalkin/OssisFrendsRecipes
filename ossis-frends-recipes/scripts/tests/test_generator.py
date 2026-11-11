"""Unit tests for invariants the corpus loops cannot reach.

The corpus loops prove agreement with Frends' own output. These prove the
things that only show up on generated files: that the two representations
stay in step, that unsupported constructs are refused rather than
approximated, and that the round trip through the generator is stable.

Run: python3 -m tests.test_generator
"""

import json
import sys
from collections import Counter
import xml.etree.ElementTree as ET

from frendsgen.spec import load_spec
from frendsgen.emit import emit, process_export, template_export
from frendsgen.validate import validate_process, ERROR
from frendsgen.parse import lift_process
from frendsgen.despec import despec, to_yaml
from frendsgen.ir import SpecError

FAILURES = []


def check(cond, msg):
    if not cond:
        FAILURES.append(msg)


def refuses(doc, needle):
    try:
        proc = load_spec(doc)
        emit(proc)
    except SpecError as exc:
        check(needle in str(exc),
              f"refusal for {needle!r} did not name it: {exc}")
        return
    FAILURES.append(f"expected a refusal naming {needle!r}, got none")


MINIMAL = {"name": "T", "steps": [{"return": {"csharp": "1"}}]}

FULL = {
    "name": "Full",
    "modifier": "test@example.com",
    "variables": [{"name": "BaseUrl", "value": '"https://x"'},
                  {"name": "Token", "value": '""', "secret": True}],
    "steps": [
        {"assign": {"variable": "acc", "expression": {"csharp": "new JArray()"}}},
        {"while": {"name": "Pages", "condition": {"csharp": "#var.more"},
                   "max_iterations": 50, "do": [
                       {"task": {"type": "http_request",
                                 "params": {"method": "GET",
                                            "url": {"csharp": "#var.BaseUrl"},
                                            "authentication": "OAuth",
                                            "token": {"csharp": "#var.Token"},
                                            "headers": [{"name": "Accept",
                                                         "value": "application/json"}]}},
                        "name": "Fetch", "retry": 3},
                       {"decision": {"name": "OK?",
                                     "condition": {"csharp": "#result[Fetch].StatusCode == 200"},
                                     "else": [{"throw": {"message": "bad"}}]}},
                       {"foreach": {"name": "Each", "item": "row",
                                    "in": {"csharp": "#result[Fetch].Body"},
                                    "do": [{"code": {"variable": "acc",
                                                     "statement_mode": False,
                                                     "expression": {"csharp": "#var.acc"}},
                                            "name": "Collect"},
                                           {"return": {"csharp": "#var.row_index"}}]}},
                       {"return": {"csharp": "#var.more"}}]}},
        {"decision": {"name": "Any?", "condition": {"csharp": "true"},
                      "then": [{"code": {"expression": {"csharp": "{ }"}},
                                "name": "Side effect"}]}},
        {"return": {"csharp": "#var.acc"}},
    ],
}


def test_generated_files_validate():
    for doc in (MINIMAL, FULL):
        out = emit(load_spec(doc), seed=3)
        errs = [f for f in validate_process(out["process"]) if f.sev == ERROR]
        check(not errs, f"{doc['name']}: generated file has errors: {errs[:3]}")


def test_ids_agree_between_representations():
    """The point of the single walk: no id in one representation and not the
    other, and no id allocated twice."""
    out = emit(load_spec(FULL), seed=3)
    eps = json.loads(out["process"]["ElementParameters"])
    ep_ids = [e["Id"] for e in eps]
    check(len(ep_ids) == len(set(ep_ids)), "duplicate ElementParameters ids")

    root = ET.fromstring(out["process"]["Bpmn"])
    bpmn_ids, di_refs = set(), set()
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag in ("BPMNShape", "BPMNEdge"):
            di_refs.add(el.get("bpmnElement"))
        elif el.get("id") and tag not in ("definitions", "process", "BPMNDiagram",
                                          "BPMNPlane", "signalEventDefinition"):
            bpmn_ids.add(el.get("id"))

    shapes = {e["Id"] for e in eps}
    unnamed_flows = bpmn_ids - shapes
    check(all(i.startswith("Flow_") for i in unnamed_flows),
          f"BPMN ids without an ElementParameters entry that are not flows: "
          f"{sorted(unnamed_flows)[:5]}")
    check(shapes <= bpmn_ids, f"ElementParameters ids missing from BPMN: "
                              f"{sorted(shapes - bpmn_ids)[:5]}")
    check(not bpmn_ids - di_refs,
          f"BPMN elements with no DI: {sorted(bpmn_ids - di_refs)[:5]}")


def test_reproducible_for_a_seed():
    a = json.dumps(process_export(load_spec(FULL), seed=5)["Processes"][0]["Bpmn"])
    b = json.dumps(process_export(load_spec(FULL), seed=5)["Processes"][0]["Bpmn"])
    check(a == b, "same seed produced different ids")
    c = json.dumps(process_export(load_spec(FULL), seed=6)["Processes"][0]["Bpmn"])
    check(a != c, "different seeds produced identical ids")


def test_round_trip_through_the_generator():
    """Generated -> lift -> regenerate. Weaker than the corpus loops (the
    answer key is our own output) but it catches asymmetries between the
    emitter and the reverse parser.

    The first lift may legitimately reshape the tree without changing the
    graph: a decision whose branches never rejoin has no canonical tree, and
    the parser normalises it to "else-branch is the branch". So the shape
    invariant is checked on the graph, and byte-stability from the second
    iteration onwards."""
    first = emit(load_spec(FULL), seed=3)["process"]
    second = emit(lift_process(first), seed=3)["process"]
    third = emit(lift_process(second), seed=3)["process"]

    def hist(p):
        return sorted(Counter(e["Type"] for e in
                              json.loads(p["ElementParameters"])).items())
    check(hist(first) == hist(second),
          f"lift changed the shape histogram: {hist(first)} -> {hist(second)}")
    check(second["ElementParameters"] == third["ElementParameters"],
          "round trip is not stable at the second iteration (ElementParameters)")
    check(second["Bpmn"] == third["Bpmn"],
          "round trip is not stable at the second iteration (BPMN)")


def test_spec_can_express_everything_the_ir_holds():
    """despec is the inverse of load_spec: re-loading a despec'd IR and
    emitting it must give the same bytes. This is what makes a spec derived
    from a real export trustworthy."""
    import yaml
    first = emit(load_spec(FULL), seed=3)["process"]
    doc = despec(lift_process(first))
    reparsed = yaml.safe_load(to_yaml(doc))
    check(reparsed == doc, "spec did not survive a YAML round trip")
    second = emit(load_spec(reparsed), seed=3)["process"]
    third = emit(lift_process(second), seed=3)["process"]
    check(second["ElementParameters"] == third["ElementParameters"],
          "despec -> load -> emit is not stable")


def test_used_tasks_json_casing_follows_the_export_form():
    """Template exports uppercase the task GUID in UsedTasksJson (195/195 in
    the corpus); the tenant's own ProcessExport leaves it lowercase (1/1).
    SelectedTypeId and LinkedTasks[].Id are lowercase on both."""
    exp = process_export(load_spec(FULL), seed=3)
    p = exp["Processes"][0]
    used = json.loads(p["UsedTasksJson"])[0].split("/")[2]
    sel = [e for e in json.loads(p["ElementParameters"])
           if e["Type"] == 1][0]["SelectedTypeId"].split("/")[2]
    linked = exp["LinkedTasks"][p["UniqueIdentifier"]][0]["Id"]
    check(used.islower(), f"ProcessExport UsedTasksJson GUID not lowercase: {used}")
    check(sel.islower(), f"SelectedTypeId GUID not lowercase: {sel}")
    check(linked.islower(), f"LinkedTasks Id not lowercase: {linked}")
    check(used == sel == linked, "the three fields disagree on the GUID")
    tpl = template_export(load_spec(FULL), seed=3)["ProcessTemplates"][0]
    tused = json.loads(tpl["ProcessInfo"]["Process"]["UsedTasksJson"])[0].split("/")[2]
    check(tused.isupper(), f"Template UsedTasksJson GUID not uppercase: {tused}")


def test_retry_count_is_bounded():
    from frendsgen.ir import SpecError
    doc = {"name": "r", "steps": [{"task": {"type": "http_request",
           "params": {"url": "https://x"}}, "name": "t", "retry": 11}]}
    try:
        load_spec(doc)
        check(False, "retry: 11 was accepted")
    except SpecError:
        pass


def test_both_shape_vocabularies_agree():
    """The export side and the diagram side each carry a Type -> BPMN element
    map. They were derived separately; they must not drift."""
    from frendsgen.shapes import TYPE_TAGS, KIND_SIZE
    from frendsgen.diagram.shapes import TYPE_TO_SHAPE
    from frendsgen.diagram.generate import SHAPE
    from frendsgen.plan import DIAGRAM_SHAPE
    diagram = {}
    for (t, tag) in TYPE_TO_SHAPE:
        diagram.setdefault(t, set()).add(tag)
    for t, tags in TYPE_TAGS.items():
        if t in (3, 4, 16):                 # flows: no diagram shape entry needed
            continue
        check(diagram.get(t) == tags, f"Type {t}: export says {sorted(tags)}, "
                                      f"diagram says {sorted(diagram.get(t, []))}")
    for kind, size in KIND_SIZE.items():
        check(tuple(SHAPE[DIAGRAM_SHAPE[kind]][1]) == tuple(size),
              f"{kind}: size {size} vs diagram {SHAPE[DIAGRAM_SHAPE[kind]][1]}")


def test_task_profiles_select_the_binding():
    """A task GUID is per-installation. The binding must follow whatever the
    target's own export says, learned by PackageId from LinkedTasks."""
    from frendsgen.tasks import register_profile
    other = "0a1b2c3d-0000-4000-8000-00000000abcd"          # synthetic
    target = {"Processes": [{"UniqueIdentifier": "p",
                             "UsedTasksJson": json.dumps([f"/ProcessTask/{other}/v1"])}],
              "LinkedTasks": {"p": [{"Id": other, "PackageId": "Frends.HTTP.Request",
                                     "PackageVersion": "9.9.9"}]}}
    name = register_profile(target)
    check(name not in (None, "corpus"), "target export did not yield a profile")
    ids = {}
    for prof in ("corpus", name):
        doc = process_export(load_spec(FULL), seed=3, profile=prof)
        p = doc["Processes"][0]
        ids[prof] = json.loads(p["UsedTasksJson"])[0]
        linked = doc["LinkedTasks"][p["UniqueIdentifier"]][0]
        check(linked["Id"] in ids[prof], "LinkedTasks and UsedTasksJson disagree")
    check(ids[name].split("/")[2] == other, f"binding ignored the target: {ids}")
    check(ids["corpus"] != ids[name], f"profiles produced the same binding: {ids}")
    no_tasks = {"Processes": [{"UniqueIdentifier": "q", "UsedTasksJson": "[]"}],
                "LinkedTasks": {"q": []}}
    check(register_profile(no_tasks) is None, "empty export yielded a profile")


def test_envelopes():
    p = process_export(load_spec(FULL), seed=3)
    check(set(p) == {"Processes", "LinkedTasks", "LinkedSubProcess", "Version"},
          f"ProcessExport keys: {sorted(p)}")
    guid = p["Processes"][0]["UniqueIdentifier"]
    check(list(p["LinkedTasks"]) == [guid], "LinkedTasks is not keyed by the process GUID")
    check(p["LinkedTasks"][guid][0]["PackageId"] == "Frends.HTTP.Request",
          "LinkedTasks does not carry the HTTP Request package")
    check(p["Processes"][0]["ProcessVariablesJson"] is not None,
          "ProcessExport lost the Process Variables")

    t = template_export(load_spec(FULL), seed=3)
    tpl = t["ProcessTemplates"][0]
    check(tpl["ProcessVariablesJson"] is not None,
          "Template lost the Process Variables from the wrapper")
    check(tpl["ProcessInfo"]["Process"]["ProcessVariablesJson"] is None,
          "Template inner ProcessVariablesJson should be null, as in all 77 corpus files")
    check(tpl["ProcessInfo"]["Process"]["Modifier"] is not None,
          "Modifier must be non-null")


def test_refusals_name_the_element():
    refuses({"name": "T", "steps": [{"catch": {}}]}, "catch")
    refuses({"name": "T", "steps": [{"intermediate_return": {}}]}, "intermediate_return")
    refuses({"name": "T", "steps": [{"parallel_foreach": {}}]}, "parallel_foreach")
    refuses({"name": "T", "steps": [{"scheduled_resume": {}}]}, "scheduled_resume")
    refuses({"name": "T", "steps": [{"task": {"type": "sftp_read"}}]}, "sftp_read")
    refuses({"name": "T", "steps": [{"foreach": {"item": "a", "in": "b", "loop": 1}}]},
            "loop")
    refuses({"name": "T", "steps": [{"task": {"type": "http_request",
                                              "params": {"metod": "GET"}}}]}, "metod")
    refuses({"name": "T", "steps": [{"task": {"type": "http_request",
                                              "params": {"method": "TRACE"}}}]}, "TRACE")
    refuses({"name": "T", "nonsense": 1, "steps": []}, "nonsense")
    refuses({"name": "T", "trigger": "carrier_pigeon", "steps": []}, "carrier_pigeon")


def test_decision_with_a_merging_branch_gets_a_return_to_merge_to():
    """A decision whose else-branch merges back needs something after it.
    The loader appends a Return rather than leaving the graph open, so the
    _wire guard for a dangling merge should be unreachable from a spec."""
    out = emit(load_spec({"name": "T", "steps": [
        {"decision": {"name": "D", "condition": "true",
                      "then": [{"return": {"csharp": "1"}}]}}]}), seed=3)
    eps = json.loads(out["process"]["ElementParameters"])
    check(len([e for e in eps if e["Type"] == 5]) == 2,
          "expected the branch Return plus an appended merge Return")
    errs = [f for f in validate_process(out["process"]) if f.sev == ERROR]
    check(not errs, f"open merge produced an invalid file: {errs[:2]}")


def test_assign_variable_omits_use_statement_mode():
    """An Assign Variable carries no useStatementMode key: 135 of 138 30x30
    scriptTasks in the corpus omit it, 37 of 37 100x80 ones carry it."""
    out = emit(load_spec({"name": "T", "steps": [
        {"assign": {"variable": "x", "expression": {"csharp": "1"}}},
        {"code": {"variable": "y", "expression": {"csharp": "{ return 1; }"}},
         "name": "C"},
        {"return": {"csharp": "#var.y"}}]}), seed=3)
    eps = {e["Name"]: e for e in json.loads(out["process"]["ElementParameters"])}
    check("useStatementMode" not in eps["Assign x"]["Parameters"],
          "Assign Variable emitted useStatementMode")
    check("useStatementMode" in eps["C"]["Parameters"],
          "Code Task did not emit useStatementMode")


def test_both_branches_terminating_needs_no_successor():
    """The bug the reverse parser found: such a decision is itself terminal,
    so no Return may be appended after it."""
    out = emit(load_spec({"name": "T", "steps": [
        {"decision": {"name": "D", "condition": "true",
                      "then": [{"return": {"csharp": "1"}}],
                      "else": [{"throw": {"message": "no"}}]}}]}), seed=3)
    eps = json.loads(out["process"]["ElementParameters"])
    returns = [e for e in eps if e["Type"] == 5]
    check(len(returns) == 1, f"expected 1 Return, got {len(returns)}")


def test_gateway_default_and_flow_entries():
    out = emit(load_spec(FULL), seed=3)
    eps = {e["Id"]: e for e in json.loads(out["process"]["ElementParameters"])}
    root = ET.fromstring(out["process"]["Bpmn"])
    gateways = [el for el in root.iter() if el.tag.endswith("exclusiveGateway")]
    check(gateways, "no gateways in the full example")
    for gw in gateways:
        outs = [c.text for c in gw if c.tag.endswith("outgoing")]
        check(gw.get("default") in outs, f"{gw.get('id')}: default not among outgoing")
        marked = [f for f in outs if eps.get(f, {}).get("IsDefault")]
        check(marked == [gw.get("default")],
              f"{gw.get('id')}: IsDefault {marked} != default {gw.get('default')}")
    # a flow gets an entry iff it leaves a gateway
    gw_flows = {c.text for gw in gateways for c in gw if c.tag.endswith("outgoing")}
    flow_entries = {i for i, e in eps.items() if e["Type"] == 4}
    check(flow_entries == gw_flows,
          f"flow entries {sorted(flow_entries)} != gateway flows {sorted(gw_flows)}")


def test_retry_marker_matches_should_retry():
    out = emit(load_spec(FULL), seed=3)
    eps = {e["Id"]: e for e in json.loads(out["process"]["ElementParameters"])}
    root = ET.fromstring(out["process"]["Bpmn"])
    for el in root.iter():
        if not el.tag.endswith("}task"):
            continue
        marker = any(c.tag.endswith("standardLoopCharacteristics") for c in el)
        check(marker == bool(eps[el.get("id")]["ShouldRetry"]),
              f"{el.get('id')}: retry marker {marker} vs ShouldRetry")


def test_containers_carry_the_right_loop_element():
    out = emit(load_spec(FULL), seed=3)
    eps = {e["Id"]: e for e in json.loads(out["process"]["ElementParameters"])}
    want = {10: "multiInstanceLoopCharacteristics", 11: "standardLoopCharacteristics"}
    seen = set()
    for el in ET.fromstring(out["process"]["Bpmn"]).iter():
        if not el.tag.endswith("subProcess"):
            continue
        t = eps[el.get("id")]["Type"]
        seen.add(t)
        have = [c.tag.split("}")[-1] for c in el if "LoopCharacteristics" in c.tag]
        check(have == [want[t]], f"{el.get('id')}: Type {t} carries {have}")
        starts = [c for c in el if c.tag.endswith("startEvent")]
        check(len(starts) == 1 and eps[starts[0].get("id")]["Type"] == 13,
              f"{el.get('id')}: inner start event is wrong")
    check(seen == {10, 11}, f"full example should exercise both containers, saw {seen}")


# --- 6.3 constructs ---------------------------------------------------------

import glob
import os
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = [os.path.join(HERE, "fixtures", "shapes-6.3.json")]
SUB = {"name": "S", "guid": "00000000-0000-4000-8000-000000000201",
       "parameters": ["input"]}


def _six(steps, **top):
    return {"name": "T", "target": "6.3", "subprocesses": [SUB], "steps": steps, **top}


def test_fixtures_are_validator_clean():
    """Calibration: the export validator reports nothing on the 6.3.2
    reference export. A rule that fires on Frends' own output is a bug in
    the rule."""
    check(os.path.exists(FIXTURES[0]), "reference export missing")
    for f in FIXTURES:
        doc = json.load(open(f, encoding="utf-8"))
        for p in doc["Processes"]:
            out = validate_process(p)
            check(not out, f"{os.path.basename(f)}: {[str(x) for x in out][:3]}")


def _lift_emit(f):
    from frendsgen.parse import lift_file
    from frendsgen.tasks import register_profile
    doc = json.load(open(f, encoding="utf-8"))
    prof = register_profile(doc) or "corpus"
    proc = lift_file(f)[0]
    proc.unique_identifier = doc["Processes"][0]["UniqueIdentifier"]
    return doc, process_export(proc, profile=prof)


def test_fixtures_rebuild_shape_for_shape():
    """The answer key is Frends output. Lift each reference export, emit it,
    and every ElementParameters entry must come back identical by Id, except
    (a) artifacts, which the importable form does not carry, and (b) the HTTP
    Request Task, which the generator writes as the public templates have it."""
    def norm(e):
        e = dict(e)
        for k in ("Name", "Description"):
            if e[k] == "":
                e[k] = None
        return e
    for f in FIXTURES:
        doc, out = _lift_emit(f)
        a = {e["Id"]: norm(e) for e in json.loads(doc["Processes"][0]["ElementParameters"])}
        b = {e["Id"]: norm(e) for e in json.loads(out["Processes"][0]["ElementParameters"])}
        skip = {i for i, e in a.items() if e["Type"] in (22, 23)
                or (e["Type"] == 1)}
        for i in a:
            if i in skip:
                continue
            check(i in b, f"{os.path.basename(f)}: {i} (Type {a[i]['Type']}) not rebuilt")
            if i in b:
                check(a[i] == b[i], f"{os.path.basename(f)}: {i} Type {a[i]['Type']} "
                                    f"differs")
        check(not set(b) - set(a), f"{os.path.basename(f)}: extra entries "
                                   f"{sorted(set(b) - set(a))}")
        po, pg = doc["Processes"][0], out["Processes"][0]
        for k in ("TriggersJson", "ManualTriggerJson", "UsedSubprocessesJson",
                  "FrendsVersion", "ProcessExecutionVersion", "TargetFramework",
                  "PreserveReferencesAtCheckpoint"):
            check(po.get(k) == pg.get(k), f"{os.path.basename(f)}: {k} differs")
        check(doc["LinkedSubProcess"] == out["LinkedSubProcess"],
              f"{os.path.basename(f)}: LinkedSubProcess differs")
        check(not [x for x in validate_process(pg) if x.sev == ERROR],
              f"{os.path.basename(f)}: rebuilt file does not validate")


def test_fixtures_rebuild_the_same_bpmn_graph():
    """Element, event definition, parent, name and default flow of every
    node, and the source/target/name of every flow, match the original."""
    L = lambda t: t.split("}")[-1]
    skip = {"textAnnotation", "association", "group", "dataObject",
            "dataObjectReference", "dataStoreReference", "dataOutputAssociation"}

    def struct(bpmn):
        r = ET.fromstring(bpmn)
        nodes, flows = set(), []

        def walk(el, parent):
            for c in el:
                t, i = L(c.tag), c.get("id")
                if t == "sequenceFlow":
                    flows.append((c.get("sourceRef"), c.get("targetRef"),
                                  c.get("name") or None))
                elif i and t not in skip and not t.endswith(("EventDefinition",
                                                             "Characteristics")):
                    defs = tuple(L(x.tag) for x in c
                                 if L(x.tag).endswith(("EventDefinition",
                                                       "Characteristics")))
                    nodes.add((i, t, defs, parent, c.get("name") or None,
                               c.get("default")))
                    walk(c, i if t == "subProcess" else parent)
        walk(next(x for x in r if L(x.tag) == "process"), None)
        return nodes, sorted(flows)
    for f in FIXTURES:
        doc, out = _lift_emit(f)
        a = struct(doc["Processes"][0]["Bpmn"])
        b = struct(out["Processes"][0]["Bpmn"])
        check(a[0] == b[0], f"{os.path.basename(f)}: nodes differ {sorted(a[0] ^ b[0])[:3]}")
        check(a[1] == b[1], f"{os.path.basename(f)}: flows differ")


def test_fixtures_survive_the_spec_round_trip():
    """lift -> YAML spec -> load -> emit gives the same ElementParameters
    (as a multiset: regenerated ids are new)."""
    from frendsgen.parse import lift_file
    key = lambda e: json.dumps([e["Type"], e["Parameters"], e["SelectedTypeId"],
                                e["Name"] or None, e["IsDefault"]], sort_keys=True)
    for f in FIXTURES:
        a = process_export(lift_file(f)[0])
        y = to_yaml(despec(lift_file(f)[0]))
        b = process_export(load_spec(yaml.safe_load(y)))
        ca = Counter(map(key, json.loads(a["Processes"][0]["ElementParameters"])))
        cb = Counter(map(key, json.loads(b["Processes"][0]["ElementParameters"])))
        check(ca == cb, f"{os.path.basename(f)}: spec round trip lost "
                        f"{list((ca - cb).keys())[:1]}")


def test_dmn_table_rebuilds_the_reference_xml():
    """The table builder writes what the 6.3.2 editor wrote, up to the
    editor's random element ids."""
    from frendsgen.dmn import parse_dmn, build_dmn
    import re
    doc = json.load(open(FIXTURES[0], encoding="utf-8"))
    e = next(e for e in json.loads(doc["Processes"][0]["ElementParameters"])
             if e["Type"] == 21)
    t = parse_dmn(e["Parameters"]["dmnXml"], e["Parameters"]["parameters"])
    t.raw_xml = None
    xml, did, params = build_dmn(t, e["Id"])
    strip = lambda x: re.sub(r'id="(InputClause|LiteralExpression|DecisionRule|'
                             r'UnaryTests)_[a-z0-9]+"', 'id="X"', x)
    check(strip(xml) == strip(e["Parameters"]["dmnXml"]), "DMN XML differs")
    check(did == e["Parameters"]["decisionId"], "decisionId differs")
    check(params == e["Parameters"]["parameters"], "DMN parameters differ")


def test_all_shapes_example_generates_clean():
    path = os.path.join(HERE, "..", "examples", "all-shapes-6.3.yaml")
    proc = load_spec(yaml.safe_load(open(path, encoding="utf-8")))
    out = process_export(proc)
    errs = [x for x in validate_process(out["Processes"][0]) if x.sev == ERROR]
    check(not errs, f"all-shapes example: {[str(x) for x in errs][:3]}")
    types = {e["Type"] for e in json.loads(out["Processes"][0]["ElementParameters"])}
    want = {0, 1, 2, 4, 5, 6, 7, 8, 12, 13, 14, 15, 16, 17, 18, 20, 21, 24, 25, 26}
    check(want <= types, f"example misses Types {sorted(want - types)}")


def test_63_refusals():
    task = {"task": {"type": "http_request", "params": {"method": "GET", "url": "x"}}}
    refuses({"name": "T", "steps": [{"scope": {"do": [{"return": "1"}]}}]}, "6.3")
    ok_handler = {"assign": {"variable": "e", "expression": "1"}}
    refuses(_six([{"foreach": {"item": "i", "in": "x", "do": [{"return": "1"}]},
                   "on_error": {"do": ok_handler}}, {"return": "1"}]), "Foreach")
    refuses(_six([{**task, "respond_early": "1",
                   "on_error": {"do": ok_handler}}, {"return": "1"}]), "not both")
    # Frends 6.3.2 run: Process Variable values are JSON, not C#
    refuses({"name": "T", "variables": [{"name": "L", "value": "new JArray()"}],
             "steps": [{"return": "1"}]}, "not JSON")
    refuses({"name": "T", "steps": [{"assign": {"variable": "short", "expression": "1"}},
                                    {"return": "1"}]}, "C# keyword")
    # Frends 6.3.2 import: CS1977, lambda on a dynamic #var
    refuses(_six([{"code": {"statement_mode": True, "variable": "v", "expression": {
        "csharp": "{ return #var.jokes.Any(x => x != null); }"}}}, {"return": "1"}]),
            "CS1977")
    # Frends 6.3.2 import: an API Trigger with no OpenAPI document is a parse error
    refuses(_six([{"return": "1"}], trigger={"type": "api", "config": {
        "routeTemplate": "api/x/y"}}), "openApiDocument")
    # Frends 6.3.2 import refused a Catch whose handler throws
    refuses(_six([{**task, "on_error": {"do": {"throw": {"message": "x"}}}}]),
            "cannot end the Process")
    # Frends 6.3.2 compile: CS8030 for a value returned from a void Code Task
    refuses(_six([{"code": {"statement_mode": True,
                            "expression": {"csharp": "{ return 1; }"}}}]), "CS8030")
    refuses(_six([{"code": {"statement_mode": True, "variable": "v",
                            "expression": {"csharp": "{ var x = 1; }"}}}]), "must")
    refuses(_six([{**task, "on_error": {"do": [{"return": "1"}, {"return": "2"}]}}]),
            "exactly one shape")
    refuses(_six([{"call": {"subprocess": "Nope"}}]), "not bound")
    refuses(_six([{"call": {"subprocess": "S", "params": {"inptu": "x"}}}]), "inptu")
    refuses(_six([{"dmn": {"inputs": [{"expression": "#var.x"}], "rules": []}}]), "'#'")
    refuses(_six([{"shared_state": {"operation": "TryRemove", "key": "k"}}]), "TryRemove")
    refuses(_six([{"ai_connector": {}}]), "params")
    refuses(_six([{"return": "1"}], trigger={"type": "service_bus", "config": {
        "connectionString": "Endpoint=sb://x;SharedAccessKey=abc"}}), "credential")
    refuses(_six([{"return": "1"}], trigger={"type": "http", "config": {
        "routeTemplate": "/a/{{#var.x}}"}}), "plain text")
    refuses(_six([{"return": "1"}], trigger={"type": "file", "config": {"bogus": 1}}),
            "bogus")
    refuses(_six([{**task, "on_error": {"do": {"decision": {"condition": "true"}}}}]),
            "cannot be the Catch handler")
    refuses(_six([{"return": "1"}], trigger={"type": "conditional", "config": {
        "processGuid": "00000000-0000-4000-8000-000000000201"}}), "per-Tenant")
    refuses(_six([{"return": "1"}], trigger={"type": "conditional",
                                            "subprocess": "Nope"}), "not bound")
    refuses(_six([{"inclusive": {"branches": [{"name": "A", "condition": "true"},
                                              {"name": "A", "condition": "false"}]}}]),
            "unique")


def test_catch_rejoins_and_loop_closes():
    out = emit(load_spec(_six([
        {"task": {"type": "http_request", "params": {"method": "GET", "url": "x"}},
         "name": "Get", "on_error": {"do": {"assign": {"variable": "v",
                                                       "expression": "1"}}}},
        {"wait_until": {"condition": "true", "every_minutes": 5, "max_iterations": 3}},
        {"return": "1"}])))
    eps = {e["Id"]: e for e in json.loads(out["process"]["ElementParameters"])}
    plan = out["plan"]
    catch = next(n for n in plan.nodes if n.kind == "catch")
    get = next(n for n in plan.nodes if n.name == "Get")
    handler = catch.handler
    after = [f.tgt for f in plan.flows if f.src is get and f.tgt is not catch]
    back = [f.tgt for f in plan.flows if f.src is handler]
    check(after == back, "Catch handler does not rejoin at the guarded shape's successor")
    resume = next(n for n in plan.nodes if n.kind == "scheduled_resume")
    cp = next(n for n in plan.nodes if n.kind == "checkpoint")
    check([f.tgt for f in plan.flows if f.src is resume] == [cp],
          "Scheduled Resume does not loop back to its Checkpoint")
    check(eps[resume.bid]["Type"] == 25 and eps[cp.bid]["Type"] == 24,
          "long-running Types are wrong")
    check(not [x for x in validate_process(out["process"]) if x.sev == ERROR],
          "catch/loop file does not validate")


def test_caller_binds_to_a_generated_subprocess():
    from frendsgen.spec import subprocess_refs_from_export
    sub = process_export(load_spec({
        "name": "Sub", "target": "6.3", "subprocess": True,
        "unique_identifier": "00000000-0000-4000-8000-000000000555",
        "trigger": {"type": "manual", "parameters": [{"name": "count", "default": "3"}]},
        "steps": [{"return": "#trigger.data.count"}]}))
    check(sub["Processes"][0]["IsSubprocess"] is True, "IsSubprocess not set")
    refs = subprocess_refs_from_export(sub)
    check(refs.get("Sub") and refs["Sub"].guid == "00000000-0000-4000-8000-000000000555"
          and refs["Sub"].parameters == ["count"], f"binding wrong: {refs}")
    # Frends 6.3.2: a trimmed copy failed import ("can't find subprocess")
    check(refs["Sub"].manual_triggers_json == sub["Processes"][0]["ManualTriggerJson"],
          "LinkedSubProcess ManualTriggersJson is not the Subprocess's own, verbatim")
    caller = load_spec({"name": "C", "target": "6.3",
                        "steps": [{"call": {"subprocess": "Sub", "params": {"count": "2"}}},
                                  {"return": "1"}]})
    caller.subprocesses.update(refs)
    out = process_export(caller)
    p = out["Processes"][0]
    check("00000000-0000-4000-8000-000000000555" in json.loads(p["UsedSubprocessesJson"]),
          "caller does not list the Subprocess")
    check(not [x for x in validate_process(p) if x.sev == ERROR], "caller does not validate")
    refuses({"name": "S", "target": "6.3", "subprocess": True,
             "triggers": ["manual", "schedule"], "steps": [{"return": "1"}]}, "exactly one Trigger")


def test_skill_frontmatter_matches_the_pinned_description():
    """An unquoted description is cut at ` #env` (a YAML comment). Parse the
    frontmatter and compare with the text pinned in build/README.md."""
    import re
    root = os.path.join(HERE, "..", "..")
    skill = open(os.path.join(root, "SKILL.md"), encoding="utf-8").read()
    fm = yaml.safe_load(skill.split("---")[1])
    pinned = re.search(r"> (Expert knowledge for the Frends iPaaS.*?)\n",
                       open(os.path.join(root, "build", "README.md"),
                            encoding="utf-8").read()).group(1)
    check(fm["description"] == pinned, "SKILL.md description differs from the "
                                       "pinned one (unquoted '#'?)")
    check(len(fm["description"]) <= 1024, "description longer than 1024 characters")


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        n = len(FAILURES)
        try:
            t()
        except Exception as exc:
            FAILURES.append(f"{t.__name__} raised {type(exc).__name__}: {exc}")
        status = "ok  " if len(FAILURES) == n else "FAIL"
        print(f"  {status} {t.__name__}")
    print(f"\n{len(tests)} tests, {len(FAILURES)} failure(s)")
    for f in FAILURES:
        print("   ", f)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
