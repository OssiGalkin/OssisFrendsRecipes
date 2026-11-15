"""Shape catalogue.

Two sources, kept apart because they disagree above Type 20:

* the 77 public FrendsTemplates (Frends 5.7.x / 6.0.2): the Type -> BPMN tag
  join that this package was first built from;
* a reference export made in the Frends 6.3.2 Process Editor, one shape
  of every kind (scrubbed copy in assets/fixtures/shapes-6.3.json).

The Platform API `ElementType` enum names the Types; neither source alone
gives the element each Type is drawn as. Where the two sources disagree
(Types 21-23), a (Type, element) PAIR is still unambiguous, so validation
checks the pair against the union of both tables.
"""

# --------------------------------------------------------------------------
# Frends 6.3.2: Type -> (BPMN tag or None, event definition or None, shape)
# Every row is observed in the 6.3.2 reference export except 3 (enum +
# corpus: a plain flow gets no ElementParameters entry), 9 (enum member the
# editor does not offer), 19 (corpus: the editor's scratch entry), and 18 and
# 25, which assets/fixtures/README.md describes.
# --------------------------------------------------------------------------
TYPES_63 = {
    0:  ("startEvent", None, "trigger"),
    1:  ("task", None, "task"),
    2:  ("exclusiveGateway", None, "decision"),
    3:  ("sequenceFlow", None, "sequence_flow"),
    4:  ("sequenceFlow", None, "decision_branch"),
    5:  ("endEvent", None, "return"),
    6:  ("intermediateThrowEvent", "signalEventDefinition", "throw"),
    7:  ("callActivity", None, "call_subprocess"),
    8:  ("subProcess", None, "scope"),
    9:  (None, None, "parallel_foreach"),        # enum only; not in the editor
    10: ("subProcess", None, "foreach"),
    11: ("subProcess", None, "while"),
    12: ("scriptTask", None, "assign_or_code"),
    13: ("startEvent", None, "inner_start"),
    14: ("intermediateCatchEvent", "signalEventDefinition", "catch"),
    15: ("inclusiveGateway", None, "inclusive_decision"),
    16: ("sequenceFlow", None, "inclusive_branch"),
    17: ("endEvent", "signalEventDefinition", "intermediate_return"),
    18: (None, None, "unhandled_error_subprocess"),  # Id "globalErrorHandler"
    19: (None, None, "test_task"),                   # Id "FrendsTestElementId"
    20: ("businessRuleTask", None, "shared_state"),
    21: ("businessRuleTask", None, "dmn"),
    22: ("dataObjectReference", None, "data_object"),
    23: ("dataStoreReference", None, "data_store"),
    24: ("intermediateCatchEvent", "messageEventDefinition", "checkpoint"),
    25: ("intermediateCatchEvent", "timerEventDefinition", "scheduled_resume"),
    26: ("intermediateCatchEvent", "messageEventDefinition", "signal_resume"),
    27: ("task", None, "ai_connector"),
}

# The 5.7/6.0 corpus, where it differs from 6.3.2.
TYPES_CORPUS_DIFF = {
    21: ("dataObjectReference", None, "data_object"),     # 40 obs
    22: ("dataStoreReference", None, "data_store"),       # 73 obs
}

# Type -> every tag it has been seen on, across both sources.
TYPE_TAGS = {}
for _t, (_tag, _d, _s) in list(TYPES_63.items()) + list(TYPES_CORPUS_DIFF.items()):
    if _tag:
        TYPE_TAGS.setdefault(_t, set()).add(_tag)

# Types that are ElementParameters entries with no diagram element, and the
# Id each one is written under.
ELEMENTLESS = {18: "globalErrorHandler", 19: "FrendsTestElementId"}

# Shapes that carry no runtime behaviour.
ARTIFACT_TYPES = {21, 22, 23}          # corpus numbering; see is_artifact()


def is_artifact(type_no, tag):
    return tag in ("dataObjectReference", "dataStoreReference")


# Backwards-compatible single-tag view, used where one answer is needed.
TYPE_TAG = {t: v[0] for t, v in TYPES_63.items() if v[0]}

# --------------------------------------------------------------------------
# Generator kinds. kind -> (Type, BPMN tag, event definition, (w, h), id prefix)
# Sizes: the only value observed for that Type (corpus or reference export).
# Containers are sized to content; their tuple is unused.
# --------------------------------------------------------------------------
KINDS = {
    "trigger":          (0,  "startEvent", None, (36, 36), "StartEvent"),
    "inner_start":      (13, "startEvent", None, (36, 36), "Event"),
    "task":             (1,  "task", None, (100, 80), "Activity"),
    "assign":           (12, "scriptTask", None, (30, 30), "Activity"),
    "code":             (12, "scriptTask", None, (100, 80), "Activity"),
    "decision":         (2,  "exclusiveGateway", None, (50, 50), "Gateway"),
    # the Exclusive Decision that closes a Checkpoint / Scheduled Resume loop
    "wait_gate":        (2,  "exclusiveGateway", None, (50, 50), "Gateway"),
    "inclusive":        (15, "inclusiveGateway", None, (50, 50), "Gateway"),
    "return":           (5,  "endEvent", None, (36, 36), "Event"),
    "throw":            (6,  "intermediateThrowEvent", "signalEventDefinition",
                         (36, 36), "Event"),
    "intermediate_return": (17, "endEvent", "signalEventDefinition", (36, 36),
                            "Event"),
    "catch":            (14, "intermediateCatchEvent", "signalEventDefinition",
                         (36, 36), "Event"),
    "foreach":          (10, "subProcess", None, (0, 0), "Activity"),
    "while":            (11, "subProcess", None, (0, 0), "Activity"),
    "scope":            (8,  "subProcess", None, (0, 0), "Activity"),
    "call_subprocess":  (7,  "callActivity", None, (100, 80), "Activity"),
    "shared_state":     (20, "businessRuleTask", None, (100, 80), "Activity"),
    "dmn":              (21, "businessRuleTask", None, (100, 80), "Activity"),
    "ai_connector":     (27, "task", None, (199, 131), "Activity"),
    "checkpoint":       (24, "intermediateCatchEvent", "messageEventDefinition",
                         (36, 36), "Event"),
    "scheduled_resume": (25, "intermediateCatchEvent", "timerEventDefinition",
                         (36, 36), "Event"),
    "signal_resume":    (26, "intermediateCatchEvent", "messageEventDefinition",
                         (36, 36), "Event"),
}

KIND_TYPE = {k: v[0] for k, v in KINDS.items()}
KIND_SIZE = {k: v[3] for k, v in KINDS.items() if v[3] != (0, 0)}
KIND_PREFIX = {k: v[4] for k, v in KINDS.items()}

# Kinds that need the 6.3 target: their serialised form comes only from the
# 6.3.2 reference export.
KINDS_63 = {"wait_gate", "intermediate_return", "catch", "scope", "call_subprocess",
            "inclusive", "shared_state", "dmn", "ai_connector", "checkpoint",
            "scheduled_resume", "signal_resume"}

# Container loop-characteristics element, by Type. 53/53 Foreach, 8/8 While
# in the corpus; the 6.3.2 Scope (Type 8) carries none.
CONTAINER_LOOP = {
    10: ("multiInstanceLoopCharacteristics", {"isSequential": "true"}),
    11: ("standardLoopCharacteristics", {}),
}
CONTAINER_TYPES = {8, 10, 11}

# The 12 keys of an ElementParameters entry, in the order Frends writes them.
# 2108/2108 corpus entries and every entry in the 6.3.2 reference export.
EP_KEYS = (
    "Id", "Type", "Parameters", "SelectedTypeId", "PromoteResultAs", "Name",
    "Description", "IsDefault", "ShouldRetry", "MaxRetryCount",
    "ShouldNotLogResult", "ShouldDispose",
)

# Trigger $type values: eleven are in the 6.3.2 reference export, Service Bus
# is described in assets/fixtures/README.md.
TRIGGER_TYPES = {
    "manual": "ManualTrigger",
    "http": "HttpTrigger",
    "api": "HttpApiTrigger",
    "file": "FileWatchTrigger",
    "schedule": "ScheduleTrigger",
    "conditional": "ConditionalTrigger",
    "mcp": "McpTrigger",
    "tcp": "TcpTrigger",
    "event_hub": "AzureEventHubTrigger",
    "rabbitmq": "RabbitMQTrigger",
    "amqp": "QueueTrigger",            # the editor names it "Queue"
    "service_bus": "ServiceBusTrigger",
}
