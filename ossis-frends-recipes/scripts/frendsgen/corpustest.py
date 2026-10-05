"""The three corpus test loops, in order of what they prove.

1. calibrate  — run the validator over untouched corpus files. Anything it
                reports there is a bug in a rule, since Frends produced them.
2. rebuild    — read every corpus instance of a supported task into the IR,
                re-emit its Parameters, and diff against Frends' own bytes.
                The answer key is Frends output, so this is not circular.
3. lift       — lift whole real Processes into the IR and regenerate. Proves
                the IR covers what real Processes use, and finds emitter bugs
                the forward path cannot.
"""

import glob
import json
import os
from collections import Counter, defaultdict

from .validate import validate_process, processes_in, ERROR
from .parse import lift_process, Unliftable
from .tasks import BUILDERS, PARSERS, task_for_type_id
from .emit import emit
from .tasks import PROFILES, register_profile
from .ir import SpecError


def _files(corpus):
    return sorted(glob.glob(os.path.join(corpus, "**", "process.json"),
                            recursive=True))


def _entries(corpus):
    """Yields (path, process, wrapper_variables, form)."""
    for f in _files(corpus):
        doc = json.load(open(f, encoding="utf-8-sig"))
        register_profile(doc)  # a GUID is per-installation; learn this file's
        if "ProcessTemplates" in doc:
            for t in doc["ProcessTemplates"]:
                yield (f, t["ProcessInfo"]["Process"],
                       t.get("ProcessVariablesJson"), "template")
        else:
            for p in doc.get("Processes", []):
                yield f, p, None, "process"


def _profile_of(p):
    """Which task-binding profile does this file use? A GUID is
    per-installation, so a file must be regenerated with its own."""
    refs = {e.get("SelectedTypeId") for e in json.loads(p["ElementParameters"])}
    for name, prof in PROFILES.items():
        if any(f"/ProcessTask/{b['guid']}/{b['version']}" in refs
               for b in prof.values()):
            return name
    return "corpus"


# --- loop 1 ----------------------------------------------------------------

def calibrate(corpus, verbose=False):
    errs, warns, n = Counter(), Counter(), 0
    detail = defaultdict(list)
    for f, p, _, _form in _entries(corpus):
        n += 1
        for fi in validate_process(p):
            (errs if fi.sev == ERROR else warns)[fi.rule] += 1
            if len(detail[fi.rule]) < 3:
                detail[fi.rule].append(f"{os.path.basename(os.path.dirname(f))}: {fi}")
    print(f"[calibrate] {n} corpus processes")
    print(f"  ERRORS: {sum(errs.values())} {dict(errs)}")
    print(f"  WARNS : {sum(warns.values())} {dict(warns)}")
    if verbose:
        for rule, msgs in sorted(detail.items()):
            for m in msgs:
                print("   ", m)
    return sum(errs.values())


# --- loop 2 ----------------------------------------------------------------

def rebuild_params(corpus, verbose=False):
    """Round-trip every supported-task instance through the IR and diff."""
    total = ok = 0
    bad = []
    for f, p, _, _form in _entries(corpus):
        for e in json.loads(p["ElementParameters"]):
            key = task_for_type_id(e.get("SelectedTypeId") or "")
            if e["Type"] != 1 or key is None:
                continue
            total += 1
            original = json.dumps(e["Parameters"], separators=(",", ":"),
                                  ensure_ascii=False)
            try:
                rebuilt = json.dumps(BUILDERS[key](PARSERS[key](e["Parameters"])),
                                     separators=(",", ":"), ensure_ascii=False)
            except Exception as exc:
                bad.append((f, e["Id"], f"{type(exc).__name__}: {exc}"))
                continue
            if rebuilt == original:
                ok += 1
            else:
                bad.append((f, e["Id"], _first_diff(original, rebuilt)))
    print(f"[rebuild] {ok}/{total} task parameter payloads byte-identical")
    for f, i, why in bad[:8 if not verbose else len(bad)]:
        print(f"   {os.path.basename(os.path.dirname(f))} {i}: {why}")
    return total - ok


def _first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return f"differs at {i}: ...{a[max(0,i-40):i+40]!r} vs ...{b[max(0,i-40):i+40]!r}"
    return f"length {len(a)} vs {len(b)}"


# --- loop 3 ----------------------------------------------------------------

def lift_and_regenerate(corpus, verbose=False):
    """Lift whole Processes into the IR, regenerate, compare structure."""
    lifted = failed = identical = 0
    reasons = Counter()
    mismatch = []
    for f, p, pvj, form in _entries(corpus):
        try:
            ir = lift_process(p, pvj)
        except (Unliftable, SpecError, KeyError, StopIteration) as exc:
            failed += 1
            reasons[f"{type(exc).__name__}: {str(exc)[:70]}"] += 1
            continue
        lifted += 1
        try:
            out = emit(ir, seed=1, profile=_profile_of(p))
        except Exception as exc:
            mismatch.append((f, f"emit failed: {type(exc).__name__}: {exc}"))
            continue
        errs = [x for x in validate_process(out["process"]) if x.sev == ERROR]
        if errs:
            mismatch.append((f, f"regenerated file fails validation: {errs[0]}"))
            continue
        a = _histogram(p["ElementParameters"])
        b = _histogram(out["process"]["ElementParameters"])
        if a != b:
            mismatch.append((f, f"Type histogram {dict(a)} -> {dict(b)}"))
            continue
        if _task_payloads(p) != _task_payloads(out["process"]):
            mismatch.append((f, "task parameter payloads differ"))
            continue
        # Identity of the referenced tasks must match exactly. Casing is a
        # separate question: template exports uppercase the GUID here,
        # ProcessExports leave it lowercase, so it is checked per form.
        want = sorted(u.lower() for u in json.loads(p["UsedTasksJson"]))
        got = sorted(u.lower() for u in json.loads(out["process"]["UsedTasksJson"]))
        if want != got:
            mismatch.append((f, f"UsedTasksJson {p['UsedTasksJson']} -> "
                                f"{out['process']['UsedTasksJson']}"))
            continue
        for u in json.loads(p["UsedTasksJson"]):
            guid = u.split("/")[2]
            expected_upper = (form == "template")
            if guid.isupper() != expected_upper:
                mismatch.append((f, f"{form} export has "
                                    f"{'upper' if guid.isupper() else 'lower'}case "
                                    f"UsedTasksJson GUID"))
                break
        identical += 1
    print(f"[lift] {lifted} of {lifted+failed} corpus processes fit the IR; "
          f"{identical} regenerate with an identical Type histogram, "
          f"byte-identical task payloads and matching UsedTasksJson")
    if verbose:
        print("  not liftable (expected — the IR is deliberately narrow):")
        for r, c in reasons.most_common(12):
            print(f"    {c:>3}  {r}")
    for f, why in mismatch[:8]:
        print(f"   MISMATCH {os.path.basename(os.path.dirname(f))}: {why}")
    return len(mismatch)


# Types the IR can emit. Artifacts (21/22/23), the editor's test element (19)
# and the unsupported shapes are dropped by any spec-driven regeneration, so
# comparing them would only re-measure a documented limitation.
IR_TYPES = {0, 1, 2, 4, 5, 6, 10, 11, 12, 13}


def _histogram(ep_json):
    return Counter(e["Type"] for e in json.loads(ep_json)
                   if e["Type"] in IR_TYPES)


def _task_payloads(p):
    return sorted(json.dumps(e["Parameters"], separators=(",", ":"),
                             ensure_ascii=False)
                  for e in json.loads(p["ElementParameters"]) if e["Type"] == 1)


def run_all(corpus, verbose=False):
    bad = 0
    bad += calibrate(corpus, verbose)
    bad += rebuild_params(corpus, verbose)
    bad += lift_and_regenerate(corpus, verbose)
    return bad
