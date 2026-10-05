"""Shape catalogue.

Every fact here was recovered by joining ElementParameters to the BPMN tag of
the same id across the 77 public FrendsTemplates process.json files
(Frends 5.7.0 / 5.7.2 / 5.7.3 / 6.0.2). See README for the survey output.
"""

# Frends shape Type -> BPMN tag, as observed in the corpus.
TYPE_TAG = {
    0:  "startEvent",              # Trigger                          78 obs
    1:  "task",                    # Task                            311
    2:  "exclusiveGateway",        # Exclusive Decision              286
    4:  "sequenceFlow",            # Sequence Flow                   572
    5:  "endEvent",                # Return                          292
    6:  "intermediateThrowEvent",  # Throw                           115
    10: "subProcess",              # Foreach                          53
    11: "subProcess",              # While                             8
    12: "scriptTask",              # Assign Variable / Code Task     175
    13: "startEvent",              # container inner start            61
    15: "inclusiveGateway",        # Inclusive Decision (unsupported)  1
    16: "sequenceFlow",            # inclusive branch (unsupported)    3
    20: "businessRuleTask",        # Shared State (unsupported)        3
    21: "dataObjectReference",     # artifact                         40
    22: "dataStoreReference",      # artifact                         73
    23: "dataStoreReference",      # artifact                          4
}

ARTIFACT_TYPES = {21, 22, 23}
UNSUPPORTED_TYPES = {15, 16, 20}

# IR kind -> Frends Type
KIND_TYPE = {
    "trigger": 0,
    "task": 1,
    "decision": 2,
    "return": 5,
    "throw": 6,
    "foreach": 10,
    "while": 11,
    "assign": 12,
    "code": 12,
    "inner_start": 13,
}

# IR kind -> (width, height). Every value below is the only one observed for
# that Type in the corpus; containers are sized to their content instead.
KIND_SIZE = {
    "trigger": (36, 36),
    "inner_start": (36, 36),
    "task": (100, 80),
    "decision": (50, 50),
    "return": (36, 36),
    "throw": (36, 36),
    "assign": (30, 30),      # Assign Variable is the small scriptTask
    "code": (100, 80),       # Code Task is the full-size scriptTask
}

# Container loop-characteristics element, by Type. Perfect correlation in the
# corpus: 53/53 Foreach, 8/8 While.
CONTAINER_LOOP = {
    10: ("multiInstanceLoopCharacteristics", {"isSequential": "true"}),
    11: ("standardLoopCharacteristics", {}),
}

# The 12 keys of an ElementParameters entry, in the order Frends writes them.
# 2108/2108 entries in the corpus use exactly this tuple.
EP_KEYS = (
    "Id", "Type", "Parameters", "SelectedTypeId", "PromoteResultAs", "Name",
    "Description", "IsDefault", "ShouldRetry", "MaxRetryCount",
    "ShouldNotLogResult", "ShouldDispose",
)

# Id prefixes, matching bpmn.io / Frends editor conventions.
KIND_PREFIX = {
    "trigger": "StartEvent",
    "inner_start": "Event",
    "task": "Activity",
    "assign": "Activity",
    "code": "Activity",
    "foreach": "Activity",
    "while": "Activity",
    "decision": "Gateway",
    "return": "Event",
    "throw": "Event",
}
