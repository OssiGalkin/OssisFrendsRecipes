"""Supported task parameter schemas.

Only one task is supported, chosen by corpus coverage rather than importance:
Frends.HTTP.Request appears in 30 of the 77 public templates, 82 shape
instances, and all 82 use exactly the key set and key order below. That is
enough evidence to rebuild it byte-identically; no other task has it.

Adding a task means adding an entry here plus enough real instances to run
the rebuild test against. Without those instances, don't add it.
"""

from typing import Any, Dict
from .ir import SpecError, VALID_MODES

# A task GUID is per-installation, not global. The same Frends.HTTP.Request
# has one GUID in the public templates (package 1.1.2) and a different one in
# every tenant. A file generated with the wrong GUID points at a task the
# target does not have, so the binding is a *profile*, chosen per target, not
# a constant.
#
# Only the public-corpus profile ships here. A profile for your own tenant is
# read at run time from any Process or Template you export from it
# (`generate --tasks-from my-export.json`); nothing tenant-specific is stored.
#
# The parameter schema is identical across installations seen so far, which
# is what makes one builder serve every profile.
PROFILES = {
    "corpus": {
        "http_request": {
            "guid": "d2f2020e-4ce6-4e5f-879f-ef34e57c9fca",
            "version": "v1",
            "package_version": "1.1.2",
        },
    },
}
DEFAULT_PROFILE = "corpus"

TASK_META = {
    "http_request": {
        "package_id": "Frends.HTTP.Request",
        "name": "Frends.HTTP.Request.HTTP.Request(Input, Options, CancellationToken)",
        "framework": ".NETCoreApp",
    },
}


def _linked_task_lists(doc: Dict[str, Any]):
    """Yield (linked_tasks, used_refs) for every process in either export form."""
    import json as _json
    for p in doc.get("Processes", []) or []:
        yield ((doc.get("LinkedTasks") or {}).get(p.get("UniqueIdentifier"), []),
               _json.loads(p.get("UsedTasksJson") or "[]"))
    for t in doc.get("ProcessTemplates", []) or []:
        info = t.get("ProcessInfo") or {}
        p = info.get("Process") or {}
        yield ((info.get("LinkedTasks") or {}).get(p.get("UniqueIdentifier"), []),
               _json.loads(p.get("UsedTasksJson") or "[]"))


def profile_from_export(doc: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """Read the task bindings an export carries, matched by PackageId.

    LinkedTasks is the only place an export names a task in words, so it is
    the only honest way to learn an installation's GUIDs."""
    by_package = {m["package_id"]: k for k, m in TASK_META.items()}
    prof: Dict[str, Dict[str, str]] = {}
    for linked, used in _linked_task_lists(doc):
        for lt in linked or []:
            key = by_package.get(lt.get("PackageId"))
            if key is None:
                continue
            guid = (lt.get("Id") or "").lower()
            version = "v1"
            for ref in used:
                parts = ref.split("/")
                if len(parts) == 4 and parts[2].lower() == guid:
                    version = parts[3]
            prof[key] = {"guid": guid, "version": version,
                         "package_version": lt.get("PackageVersion") or ""}
    return prof


def register_profile(doc: Dict[str, Any], name: str = None):
    """Register the bindings found in `doc`. Returns the profile name, or None
    if the export binds no supported task (or only the ones already known)."""
    prof = profile_from_export(doc)
    if not prof:
        return None
    for known, kp in PROFILES.items():
        if all(kp.get(k, {}).get("guid") == v["guid"] for k, v in prof.items()):
            return known
    name = name or "export:" + next(iter(prof.values()))["guid"][:8]
    PROFILES[name] = prof
    return name


def binding(task: str, profile: str = DEFAULT_PROFILE):
    if profile not in PROFILES:
        raise SpecError(f"unknown task profile {profile!r}. Known: "
                        f"{sorted(PROFILES)}")
    if task not in PROFILES[profile]:
        raise SpecError(f"task {task!r} has no binding in profile {profile!r}")
    b, meta = PROFILES[profile][task], TASK_META[task]
    # SelectedTypeId always uses the lowercase GUID (324/324 corpus, 1/1 tenant).
    return {
        "selected_type_id": f"/ProcessTask/{b['guid']}/{b['version']}",
        "linked": {
            "Id": b["guid"],
            "PackageId": meta["package_id"],
            "PackageVersion": b["package_version"],
            "Name": meta["name"],
            "FrameworkIdentifier": meta["framework"],
        },
    }


def task_for_type_id(type_id: str):
    """Any known GUID resolves back to its logical task, whichever profile."""
    for prof in PROFILES.values():
        for key, b in prof.items():
            if type_id == f"/ProcessTask/{b['guid']}/{b['version']}":
                return key
    return None


# Kept for callers that only need the set of supported task keys.
TASKS = {k: {"selected_type_id":
             f"/ProcessTask/{PROFILES[DEFAULT_PROFILE][k]['guid']}/v1"}
         for k in PROFILES[DEFAULT_PROFILE]}

# name -> (section, mode, default). Order is the corpus order and matters for
# a byte-identical rebuild.
_INPUT = [
    ("method",        "Method",       "select",  "GET"),
    ("result_method", "ResultMethod", "select",  "JToken"),
    ("url",           "Url",          "text",    ""),
    ("message",       "Message",      "text",    ""),
]
_OPTIONS = [
    ("authentication",           "Authentication",                        "select",  "None"),
    ("username",                 "Username",                              "text",    ""),
    ("password",                 "Password",                              "text",    ""),
    ("token",                    "Token",                                 "text",    ""),
    ("certificate_source",       "ClientCertificateSource",               "select",  "CertificateStore"),
    ("certificate_file_path",    "ClientCertificateFilePath",             "text",    ""),
    ("certificate_base64",       "ClientCertificateInBase64",             "text",    ""),
    ("certificate_key_phrase",   "ClientCertificateKeyPhrase",            "text",    ""),
    ("certificate_thumbprint",   "CertificateThumbprint",                 "text",    ""),
    ("load_entire_chain",        "LoadEntireChainForCertificate",         "toggle",  True),
    ("timeout_seconds",          "ConnectionTimeoutSeconds",              "integer", 30),
    ("follow_redirects",         "FollowRedirects",                       "toggle",  True),
    ("allow_invalid_certificate", "AllowInvalidCertificate",              "toggle",  False),
    ("allow_invalid_charset",    "AllowInvalidResponseContentTypeCharSet", "toggle", False),
    ("throw_on_error",           "ThrowExceptionOnErrorResponse",         "toggle",  False),
    ("automatic_cookie_handling", "AutomaticCookieHandling",              "toggle",  True),
]

_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}


def _cell(raw: Any, default_mode: str, default_value: Any) -> Dict[str, Any]:
    """Accept `"x"`, `{"mode": .., "value": ..}` or absence."""
    if raw is None:
        return {"mode": default_mode, "value": default_value}
    if isinstance(raw, dict):
        if set(raw) == {"mode", "value"}:
            return {"mode": raw["mode"], "value": raw["value"]}
        if len(raw) == 1:
            (m, v), = raw.items()
            if m in VALID_MODES:
                return {"mode": m, "value": v}
        raise SpecError(f"field must be {{mode, value}} or {{<mode>: value}}, "
                        f"got {sorted(raw)}")
    return {"mode": default_mode, "value": raw}


def build_http_request(spec: Dict[str, Any]) -> Dict[str, Any]:
    unknown = set(spec) - {n for n, _, _, _ in _INPUT} - {n for n, _, _, _ in _OPTIONS} - {"headers"}
    if unknown:
        raise SpecError(f"http_request: unknown parameter(s) {sorted(unknown)}")

    inp: Dict[str, Any] = {}
    for key, field, mode, dflt in _INPUT:
        inp[field] = _cell(spec.get(key), mode, dflt)
    if inp["Method"]["value"] not in _METHODS:
        raise SpecError(f"http_request: unsupported method {inp['Method']['value']!r}")

    headers = []
    for h in spec.get("headers", []) or []:
        if not isinstance(h, dict) or set(h) - {"name", "value"}:
            raise SpecError("http_request: each header needs name and value")
        headers.append({"Name": _cell(h.get("name"), "text", ""),
                        "Value": _cell(h.get("value"), "text", "")})
    inp["Headers"] = headers

    opt: Dict[str, Any] = {}
    for key, field, mode, dflt in _OPTIONS:
        opt[field] = _cell(spec.get(key), mode, dflt)

    return {"input": inp, "options": opt, "cancellationToken": None}


def parse_http_request(params: Dict[str, Any]) -> Dict[str, Any]:
    """Real export -> spec dict. Used by the rebuild test and reverse parser."""
    out: Dict[str, Any] = {}
    inp, opt = params["input"], params["options"]
    for key, field, mode, dflt in _INPUT:
        c = inp[field]
        out[key] = c["value"] if (c["mode"] == mode and c["value"] != dflt or
                                  c["mode"] == mode) else dict(c)
        if c["mode"] != mode:
            out[key] = {"mode": c["mode"], "value": c["value"]}
    for key, field, mode, dflt in _OPTIONS:
        c = opt[field]
        out[key] = {"mode": c["mode"], "value": c["value"]} if c["mode"] != mode else c["value"]
    if inp.get("Headers"):
        out["headers"] = [
            {"name": h["Name"]["value"] if h["Name"]["mode"] == "text" else dict(h["Name"]),
             "value": h["Value"]["value"] if h["Value"]["mode"] == "text" else dict(h["Value"])}
            for h in inp["Headers"]]
    return out


BUILDERS = {"http_request": build_http_request}
PARSERS = {"http_request": parse_http_request}
