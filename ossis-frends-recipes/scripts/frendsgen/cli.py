"""Command line interface."""

import argparse
import json
import sys

from .spec import load_file
from .emit import process_export, template_export
from .validate import validate_process, processes_in, ERROR
from .corpustest import run_all, calibrate, rebuild_params, lift_and_regenerate
from .tasks import PROFILES, DEFAULT_PROFILE, register_profile
from .ir import SpecError
from .parse import lift_file
from .despec import despec, to_yaml


def _generate(args) -> int:
    try:
        proc = load_file(args.spec)
    except SpecError as exc:
        print(f"spec error: {exc}", file=sys.stderr)
        return 2
    if args.fresh:
        import uuid
        proc.name = f"{proc.name} {uuid.uuid4().hex[:6]}"
    profile = DEFAULT_PROFILE
    if args.tasks_from:
        src = json.load(open(args.tasks_from, encoding="utf-8-sig"))
        profile = register_profile(src)
        if profile is None:
            print(f"{args.tasks_from}: no supported task is linked in this "
                  f"export, so it cannot supply task GUIDs. Export a Process "
                  f"that uses the task(s) your spec needs.", file=sys.stderr)
            return 2
    overrides = {}
    if args.graph_json is not None:
        overrides["GraphJson"] = args.graph_json
    if args.fill_nullable:
        overrides.setdefault("GraphJson", "{}")
        overrides.update({"TagString": "", "AssemblyName": "",
                          "PackageId": "", "PackageVersion": ""})
    try:
        doc = (template_export if args.form == "template" else process_export)(
            proc, seed=args.seed, overrides=overrides or None,
            profile=profile)
    except SpecError as exc:
        print(f"spec error: {exc}", file=sys.stderr)
        return 2

    findings = []
    for p in processes_in(doc):
        findings.extend(validate_process(p))
    errors = [f for f in findings if f.sev == ERROR]
    for f in findings:
        print(f"  {f}", file=sys.stderr)
    if errors and not args.force:
        print(f"{len(errors)} error(s); not writing. Use --force to write anyway.",
              file=sys.stderr)
        return 1

    text = json.dumps(doc, ensure_ascii=False, indent=2)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(text)

    import hashlib
    raw = text.encode("utf-8")
    print(f"wrote {args.out}")
    print(f"  form   : {args.form}")
    print(f"  bytes  : {len(raw)}")
    print(f"  md5    : {hashlib.md5(raw).hexdigest()}")
    print(f"  process: {processes_in(doc)[0]['UniqueIdentifier']}")
    used = json.loads(processes_in(doc)[0]["UsedTasksJson"])
    if used:
        print(f"  tasks  : profile '{profile}' -> "
              f"{', '.join(u.split('/')[2] for u in used)}")
        print("           A task GUID is per-installation. This file will only "
              "bind in a tenant that has these ids (see --tasks-from).")
    print("  Confirm both byte count and md5 at the tenant before reading "
          "anything into an import failure.")
    return 0


def _validate(args) -> int:
    rc = 0
    for path in args.files:
        doc = json.load(open(path, encoding="utf-8-sig"))
        for p in processes_in(doc):
            findings = validate_process(p)
            for f in findings:
                print(f"{path}: {f}")
            if any(f.sev == ERROR for f in findings):
                rc = 1
        if rc == 0:
            print(f"{path}: OK")
    return rc


def _selftest(args) -> int:
    loops = {"all": run_all, "calibrate": calibrate,
             "rebuild": rebuild_params, "lift": lift_and_regenerate}
    return 1 if loops[args.loop](args.corpus, args.verbose) else 0


def _lift(args) -> int:
    for proc in lift_file(args.file):
        if args.spec:
            text = to_yaml(despec(proc))
            if args.out:
                open(args.out, "w", encoding="utf-8").write(text)
                print(f"wrote {args.out}")
            else:
                print(text)
        else:
            print(json.dumps(_ir_summary(proc), indent=2, ensure_ascii=False))
    return 0


def _ir_summary(proc):
    def seq(nodes):
        out = []
        for n in nodes:
            d = {"kind": n.kind, "name": n.name}
            if n.kind == "task":
                d["task"] = n.task
            if n.kind == "decision":
                d["then"], d["else"] = seq(n.then), seq(n.otherwise)
            if n.kind in ("foreach", "while"):
                d["do"] = seq(n.body)
            out.append(d)
        return out
    return {"name": proc.name, "trigger": proc.trigger.trigger_type,
            "variables": [v.name for v in proc.variables], "steps": seq(proc.body)}


def _picture(args) -> int:
    """Any export (or .bpmn) -> SVG, drawn from the layout already in the file.
    No re-layout: what you see is what Frends would draw."""
    import os, re, tempfile
    from .diagram.render import render
    from .diagram.validate import main as diagram_validate
    if args.file.lower().endswith(".bpmn"):
        items = [(os.path.splitext(os.path.basename(args.file))[0],
                  open(args.file, encoding="utf-8-sig").read())]
    else:
        doc = json.load(open(args.file, encoding="utf-8-sig"))
        items = [(p.get("Name") or "process", p["Bpmn"]) for p in processes_in(doc)]
    os.makedirs(args.out, exist_ok=True)
    for name, xml in items:
        stem = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "process"
        with tempfile.TemporaryDirectory() as td:
            tmp = os.path.join(td, stem + ".bpmn")
            open(tmp, "w", encoding="utf-8").write(xml)
            svg = render(tmp)
            if args.check:
                diagram_validate([tmp])
        dst = os.path.join(args.out, stem + ".svg")
        open(dst, "w", encoding="utf-8").write(svg)
        print(f"wrote {dst}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="frendsgen",
                                 description="Generate Frends Process exports from a spec.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="spec -> export file")
    g.add_argument("spec")
    g.add_argument("-o", "--out", default="process.json")
    g.add_argument("--form", choices=["process", "template"], default="process")
    g.add_argument("--seed", type=int, default=0,
                   help="id-generation seed; ids are reproducible for a given seed")
    g.add_argument("--graph-json", default=None,
                   help="override the GraphJson field. Defaults are the "
                        "observed ones: \"\" on the Process path (null and "
                        "\"{}\" are both rejected there), null on the "
                        "Template path. For bisecting only.")
    g.add_argument("--fill-nullable", action="store_true",
                   help="for bisecting only: fill every field that is null throughout the corpus "
                        "(GraphJson, TagString, AssemblyName, PackageId, "
                        "PackageVersion) with an empty value")
    g.add_argument("--tasks-from", metavar="EXPORT",
                   help="read task GUIDs from a Process or Template exported "
                        "from the TARGET tenant. A task GUID is "
                        "per-installation: without this the file binds to the "
                        "GUIDs of the public templates and will only import "
                        "where those exist.")
    g.add_argument("--fresh", action="store_true",
                   help="for test imports: also give the Process a unique name "
                        "(the GUID is always new unless the spec pins it). A "
                        "repeated identity has returned a stale earlier error.")
    g.add_argument("--force", action="store_true")
    g.set_defaults(func=_generate)

    v = sub.add_parser("validate", help="check an export file")
    v.add_argument("files", nargs="+")
    v.set_defaults(func=_validate)

    s = sub.add_parser("selftest", help="run the corpus test loops")
    s.add_argument("corpus", help="directory containing FrendsTemplates")
    s.add_argument("--loop", choices=["all", "calibrate", "rebuild", "lift"],
                   default="all")
    s.add_argument("-v", "--verbose", action="store_true")
    s.set_defaults(func=_selftest)

    l = sub.add_parser("lift", help="real export -> IR summary (review point)")
    l.add_argument("file")
    l.add_argument("--spec", action="store_true",
                   help="emit a full spec document instead of a summary")
    l.add_argument("-o", "--out")
    l.set_defaults(func=_lift)

    pic = sub.add_parser("picture",
                         help="export or .bpmn -> SVG, from the file's own layout")
    pic.add_argument("file")
    pic.add_argument("-o", "--out", default=".", help="output directory")
    pic.add_argument("--check", action="store_true",
                     help="also run the diagram (geometry) validator")
    pic.set_defaults(func=_picture)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
