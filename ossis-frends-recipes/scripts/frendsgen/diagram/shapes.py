"""Frends shape vocabulary.

Everything here was derived by correlating ElementParameters[].Type with the
BPMN element carrying the same Id across the corpus (tools/discover_types.py).
The numbers themselves are public after all: the Platform API reference lists the
`ElementType` enum, and 0..20 match this table exactly. What the docs do not give
is the BPMN element each type is drawn as, which is what the join recovers.
Above 20 the enum has since shifted (it now reads 21 Dmn, 22 DataObjectReference,
23 DataStoreReference, 24 NativeAi), so the artifact entries below are correct for
a 5.7/6.0 corpus and should be re-derived against a newer one.

Key -> (ElementParameters.Type, BPMN localname). A (Type, None) key matches any
element carrying that Type.

Three entries would mislead a reader who trusted element names (all confirmed
against this corpus, not assumed):

  * Type 12 is BOTH Assign Variable and Code Task, both `scriptTask`. The only
    discriminator is DI width: 30x30 is Assign Variable, 100x80 is Code Task.
    Handled in extract.classify(), not here.
  * `businessRuleTask` is Shared State Task, not DMN -- SelectedTypeId is
    AddOrUpdate / TryGetValue.
  * Throw and Intermediate Return are the same element (intermediateThrowEvent
    + signalEventDefinition, Type 6) and both carry zero outgoing flows, even
    Intermediate Return, which continues executing. See AMBIGUOUS below.
"""

TYPE_TO_SHAPE = {
    # --- events ---
    (0, 'startEvent'): 'trigger',            # 36x36, SelectedTypeId = Manual/Http/Schedule/HttpApi
    (13, 'startEvent'): 'scope_trigger',     # 36x36, the Trigger inside a container; name always empty
    (5, 'endEvent'): 'return',               # 36x36, SelectedTypeId None | HttpResult | Expression
    (6, 'intermediateThrowEvent'): 'throw',  # 36x36 + signalEventDefinition

    # --- activities ---
    (1, 'task'): 'task',                     # 100x80, SelectedTypeId /ProcessTask/<guid>/vN
    (12, 'scriptTask'): 'code_task',         # overridden by width in classify()
    (20, 'businessRuleTask'): 'shared_state_task',   # NOT DMN

    # --- decisions ---
    (2, 'exclusiveGateway'): 'decision',     # 50x50
    (15, 'inclusiveGateway'): 'inclusive_decision',  # 50x50

    # --- scopes / containers ---
    (10, 'subProcess'): 'foreach',           # labels "For each ..."
    (11, 'subProcess'): 'while',             # labels "While ... remain"

    # --- sequence flows ---
    (4, 'sequenceFlow'): 'sequence_flow',            # labelled branch off an exclusive decision
    (16, 'sequenceFlow'): 'sequence_flow',           # labelled branch off an inclusive decision

    # --- artifacts (documentation only, dropped from the layout-free spec) ---
    (21, 'dataObjectReference'): 'data_object_reference',
    (22, 'dataStoreReference'): 'data_store_reference',
    (23, 'dataStoreReference'): 'data_store_reference',
}

# Used when an element has no ElementParameters entry at all. That is NORMAL for
# unlabelled sequence flows (697 of them in this corpus) and for BPMN
# infrastructure; it is not an error.
BPMN_FALLBACK_SHAPE = {
    'sequenceFlow': 'sequence_flow',
    'startEvent': 'trigger',
    'endEvent': 'return',
    'task': 'task',
    'scriptTask': 'code_task',
    'subProcess': 'scope',
    'exclusiveGateway': 'decision',
    'inclusiveGateway': 'inclusive_decision',
    'intermediateThrowEvent': 'throw',
    'businessRuleTask': 'shared_state_task',
}

# Shapes the docs describe but which do NOT occur in this corpus, so their Type
# numbers are unknown. The extractor reports any unseen Type loudly rather than
# guessing one of these. Catch is added from the docs (boundaryEvent +
# errorEventDefinition) and is marked doc-derived, not corpus-derived.
NOT_IN_CORPUS = [
    'catch', 'scope', 'call_subprocess', 'dmn_task', 'ai_connector',
    'checkpoint', 'scheduled_resume', 'signal_resume',
]

# Genuinely indistinguishable in an export: Throw and Intermediate Return share
# element, Type, event definition and outgoing-flow count (zero). Every Type 6
# in this corpus reads as a Throw from its label, but nothing in the XML proves
# it. The generator can emit either; the extractor always reports 'throw'.
AMBIGUOUS = {
    'throw': 'Intermediate Return is the same element and Type; not separable '
             'from the XML alone.',
}

# Sizes are filled in by tools/measure.py from the corpus, not hardcoded here.
