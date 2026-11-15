"""Trigger configurations.

Each template is the config that the Frends 6.3.2 reference export
(assets/fixtures/shapes-6.3.json, or its README for Service Bus) holds for that
Trigger type: the key set and
key order are Frends' own. The exports do not record which values the author
changed from the editor's defaults, so treat a template value as "what one real
Trigger had", not as the editor's default. Values that identified the author's
Tenant (routes, the condition Subprocess GUID) are emptied, and
`seasonStartDate` is filled in at generation time (below). A spec overrides any
key; an unknown key is an error, because the editor would never write it.

The same object is written twice, as Frends does: as the shape's
ElementParameters.Parameters and as TriggersJson[].config. Neither is a
{mode, value} cell.

Two rules from the docs are enforced here, because a Trigger field is plain
text at runtime:
  * no Handlebars and no #var / #result / #trigger / #process: only a bare
    `#env.Group.Name` reference is substituted;
  * a credential field (connection string, password, key, secret) must be
    empty or exactly one `#env.Group.Name` reference - never a literal.
"""

import copy
import datetime
import re
from typing import Any, Dict

from .ir import SpecError
from .shapes import TRIGGER_TYPES

TEMPLATES: Dict[str, Dict[str, Any]] = {
    "ManualTrigger": {},
    "HttpTrigger": {
        "routeTemplate": "", "allowedSchemes": "HTTPS", "auth": "ApiPolicy",
        "corsEnabled": False, "allowedOrigins": "", "httpMethod": "GET",
        "isPrivate": False},
    "HttpApiTrigger": {
        "routeTemplate": "", "isPrivate": False, "corsEnabled": False,
        "allowedOrigins": "", "allowedSchemes": "HTTP,HTTPS", "httpMethod": "GET",
        "references": ["data", "data.username", "data.httpBody", "data.httpMethod",
                       "data.httpRequestUri", "data.httpClientIp", "data.httpCookies",
                       "data.body", "data.path", "data.query", "data.header",
                       "claimsprincipal", "claimsprincipal.Identity",
                       "claimsprincipal.Identity.Name", "claimsprincipal.Claims"],
        "openApiDocument": "", "basePath": "", "auth": "ApiPolicy"},
    "FileWatchTrigger": {
        "version": 2, "dirToWatch": "", "fileMask": "*.xml",
        "includeSubDirectories": False, "maxFilesPerBatch": 1000,
        "pollIntervalSeconds": 10},
    "ScheduleTrigger": {
        "startTimeMinute": "00", "startTimeHour": "00", "endTimeMinute": "00",
        "endTimeHour": "00", "endTime": "00:00", "startTime": "00:00",
        "recurring": False, "repeatDelay": 0, "repeatDelaySeconds": 0,
        "limitToOneConcurrentExecution": True, "cycleRecurEvery": 1,
        "cycleType": "Daily", "cycleLength": 1, "seasonStartDate": None,
        "seasonEndDate": None, "cycleDaysOfWeek": "None", "cycleMonths": "None",
        "cycleDaysString": "", "cycleDayRanks": "None", "monthlyCycleType": "OnDays",
        "repeatDelayType": 1, "timeZone": "FLE Standard Time"},
    "ConditionalTrigger": {
        "pollingInterval": 60, "processGuid": "",
        "limitToOneConcurrentExecution": False, "parameters": {}},
    "McpTrigger": {
        "toolName": "", "title": "", "description": "",
        "inputSchema": "{\n  \"type\": \"object\",\n  \"properties\": {}\n}",
        "outputSchema": "", "annotations": {}},
    "TcpTrigger": {
        "dataMode": "Text", "encoding": "ASCII", "idleTimeoutSeconds": 3600,
        "connectionIdBuilder": "ClientIpAndPort", "listenPort": 38000,
        "listenAddress": "0.0.0.0", "maxConnections": 1,
        "terminationEvent": "CharacterSequence", "terminationHexString": "0a",
        "allowedIps": "0.0.0.0/0", "autoAppendTermSeq": True},
    "AzureEventHubTrigger": {
        "eventHubAuthSettings": {"authenticationMethod": "ConnectionString"},
        "eventHubName": "", "consumerGroupName": "$Default", "eventBatchSize": 1000,
        "encoding": "UTF-8", "passDataAsBase64ByteArray": False,
        "updateCheckpointImmediately": False, "maxConcurrentProcesses": 10,
        "loadBalancingStrategy": "Balanced",
        "blobCheckPointSettings": {
            "authenticationMethod": "ConnectionString",
            "storageContainerUri":
                "https://<storage-account-name>.blob.core.windows.net/<container-name>"}},
    "RabbitMQTrigger": {"maxConcurrentMessages": 1},
    # AMQP. The editor calls it "Queue"; a fresh one writes an empty config.
    "QueueTrigger": {},
    "ServiceBusTrigger": {
        "queueName": "", "connectionString": "", "maxConcurrentMessages": 10,
        "messagePrefetchCount": 1, "consumeMessageImmediately": True,
        "reply": False, "replyErrors": False, "replyTo": "",
        "retryMessageProcessingIfExceptionThrown": False},
}

# Keys a fresh Trigger does not write but the editor adds once a field is set.
# Seen in the reference export only after the author touched the field.
OPTIONAL_KEYS = {
    "ScheduleTrigger": {"timeZone"},
}

_CREDENTIAL = re.compile(r"(connectionstring|password|secret|apikey|sharedaccesskey)",
                         re.I)
_ENV_ONLY = re.compile(r"^#env\.[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$")
_FORBIDDEN = re.compile(r"(\{\{|#var\.|#var\[|#result|#trigger|#process)")


def _check(value: Any, path: str, ttype: str):
    if isinstance(value, dict):
        for k, v in value.items():
            _check(v, f"{path}.{k}", ttype)
        return
    if isinstance(value, list):
        for i, v in enumerate(value):
            _check(v, f"{path}[{i}]", ttype)
        return
    if not isinstance(value, str):
        return
    if _FORBIDDEN.search(value):
        raise SpecError(
            f"{ttype} {path}: Trigger fields are plain text. Handlebars and "
            f"#var/#result/#trigger/#process are not evaluated there; only a bare "
            f"#env.Group.Name reference is substituted.")
    key = path.rsplit(".", 1)[-1]
    if _CREDENTIAL.search(key) and value and not _ENV_ONLY.match(value.strip()):
        raise SpecError(
            f"{ttype} {path}: a credential in a Trigger must be a single "
            f"#env.Group.Name reference to a Secret Environment Variable, not a "
            f"literal value.")


def trigger_config(kind: str, overrides: Dict[str, Any], where: str):
    """-> ($type, config)"""
    if kind not in TRIGGER_TYPES:
        raise SpecError(f"{where}: unknown trigger {kind!r}; use one of "
                        f"{sorted(TRIGGER_TYPES)}")
    ttype = TRIGGER_TYPES[kind]
    cfg = copy.deepcopy(TEMPLATES[ttype])
    unknown = set(overrides or {}) - set(cfg) - OPTIONAL_KEYS.get(ttype, set())
    if unknown:
        raise SpecError(f"{where}: {kind} trigger has no field(s) {sorted(unknown)}; "
                        f"it has {sorted(cfg)}")
    cfg.update(overrides or {})
    if ttype == "ScheduleTrigger" and not cfg.get("seasonStartDate"):
        # The reference export carries a date: the day its Trigger was added.
        # A generated Trigger gets the day it was generated, unless the spec
        # sets one.
        cfg["seasonStartDate"] = datetime.date.today().isoformat()
    _check(cfg, "config", ttype)
    if ttype == "HttpApiTrigger":
        _check_api(cfg, where)
    return ttype, cfg


def _check_api(cfg, where: str):
    """An API Trigger carries the OpenAPI document of the API it serves. With
    an empty document Frends 6.3.2 refused the import with a parse-time
    NullReferenceException. The 6.3.2 reference export shows how the three
    fields relate: basePath is the document's server URL, and routeTemplate is
    basePath (without its leading slash) plus one path in the document."""
    import yaml
    doc_text = cfg.get("openApiDocument") or ""
    if not doc_text.strip():
        raise SpecError(
            f"{where}: an API Trigger needs `openApiDocument`, the OpenAPI "
            f"document of the API it serves (Frends refuses the import without "
            f"one), plus its `basePath` and the operation's `routeTemplate`.")
    try:
        doc = yaml.safe_load(doc_text)
    except yaml.YAMLError as exc:
        raise SpecError(f"{where}: openApiDocument is not YAML/JSON: {exc}")
    base = cfg.get("basePath") or ""
    servers = [sv.get("url") for sv in (doc.get("servers") or []) if isinstance(sv, dict)]
    if base not in servers:
        raise SpecError(f"{where}: basePath {base!r} is not a server url in the "
                        f"document ({servers})")
    if not base.startswith("/api/"):
        raise SpecError(f"{where}: an API's base path must start with /api/")
    route = cfg.get("routeTemplate") or ""
    prefix = base.lstrip("/")
    path = "/" + route[len(prefix):].lstrip("/") if route.startswith(prefix) else None
    paths = doc.get("paths") or {}
    method = (cfg.get("httpMethod") or "GET").lower()
    if path is None or path not in paths:
        raise SpecError(f"{where}: routeTemplate {route!r} must be basePath plus a "
                        f"path in the document; paths are {sorted(paths)}")
    if method not in {k.lower() for k in (paths[path] or {})}:
        raise SpecError(f"{where}: the document has no {method.upper()} on {path}")


def manual_parameter(p: Dict[str, Any], where: str) -> Dict[str, Any]:
    """A Manual Trigger parameter definition, as ManualTriggerJson stores it.
    Only text parameters are observed; others are refused by name."""
    unknown = set(p) - {"name", "default", "secret", "description"}
    if unknown:
        raise SpecError(f"{where}: unknown parameter key(s) {sorted(unknown)}")
    if not p.get("name"):
        raise SpecError(f"{where}: a Manual Trigger parameter needs a name")
    d = str(p.get("default", ""))
    out = {"type": "System.String", "inputType": "text",
           "parameterType": "TextParameter", "defaultValue": d,
           "displayOption": "", "conditionalDisplayProperty": "",
           "conditionalDisplayValues": [], "isInvalid": False, "invalidString": "",
           "name": p["name"], "isSecret": bool(p.get("secret", False)),
           "nonStringifiedDefaultValue": d}
    if p.get("description"):
        out["description"] = p["description"]
    return out
