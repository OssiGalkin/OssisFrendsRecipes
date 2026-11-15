"""Frends shape vocabulary for the diagram tools.

Derived by correlating ElementParameters[].Type with the BPMN element carrying
the same Id: first across the 77 public FrendsTemplates (Frends 5.7/6.0,
tools/discover_types.py), then across a reference export made in the
Frends 6.3.2 Process Editor with one shape of every kind
(assets/fixtures/shapes-6.3.json, scrubbed). The Platform API `ElementType`
enum names the Types; neither source gives the element each is drawn as.

Key -> (ElementParameters.Type, BPMN localname). Because the key is the PAIR,
one table serves both numberings: the corpus drew Types 21/22 as artifacts,
6.3.2 draws 21 as DMN and 22/23 as the artifacts. No pair collides.

Facts a reader would get wrong from element names alone:

  * Type 12 is BOTH Assign Variable and Code Task, both `scriptTask`. The
    discriminator is the presence of `useStatementMode` (or DI width: 30x30
    Assign Variable, 100x80 Code Task). Handled in extract.classify().
  * `businessRuleTask` is Shared State (20) AND DMN (21). Only Type separates.
  * Catch is NOT a boundaryEvent. It is an intermediateCatchEvent with a
    signalEventDefinition, reached by an ordinary sequence flow from the shape
    it guards (Task, Scope or Call Subprocess). Its single successor rejoins at
    the guarded shape's other successor.
  * Intermediate Return is an endEvent + signalEventDefinition (Type 17), NOT
    the Throw element. The guarded activity gets a second outgoing flow to it.
  * Checkpoint (24) and Signal Resume (26) share element and event definition
    (messageEventDefinition); only Type separates them. Scheduled Resume (25)
    is the timerEventDefinition one, and normally loops back to a Checkpoint.
"""

TYPE_TO_SHAPE = {
    # --- events ---
    (0, 'startEvent'): 'trigger',            # 36x36, SelectedTypeId = Manual/Http/Schedule/HttpApi
    (13, 'startEvent'): 'scope_trigger',     # 36x36, the Trigger inside a container; name always empty
    (5, 'endEvent'): 'return',               # 36x36, SelectedTypeId None | HttpResult | Expression
    (6, 'intermediateThrowEvent'): 'throw',  # 36x36 + signalEventDefinition
    (17, 'endEvent'): 'intermediate_return',  # 6.3.2: endEvent + signalEventDefinition
    (14, 'intermediateCatchEvent'): 'catch',  # 6.3.2: + signalEventDefinition
    (24, 'intermediateCatchEvent'): 'checkpoint',        # + messageEventDefinition
    (25, 'intermediateCatchEvent'): 'scheduled_resume',  # + timerEventDefinition
    (26, 'intermediateCatchEvent'): 'signal_resume',     # + messageEventDefinition

    # --- activities ---
    (1, 'task'): 'task',                     # 100x80, SelectedTypeId /ProcessTask/<guid>/vN
    (12, 'scriptTask'): 'code_task',         # overridden in classify()
    (20, 'businessRuleTask'): 'shared_state_task',
    (21, 'businessRuleTask'): 'dmn_task',            # 6.3.2
    (7, 'callActivity'): 'call_subprocess',          # 6.3.2
    (27, 'task'): 'ai_connector',                    # 6.3.2, drawn 199x131

    # --- decisions ---
    (2, 'exclusiveGateway'): 'decision',     # 50x50
    (15, 'inclusiveGateway'): 'inclusive_decision',  # 50x50

    # --- scopes / containers ---
    (10, 'subProcess'): 'foreach',           # labels "For each ..."
    (11, 'subProcess'): 'while',             # labels "While ... remain"
    (8, 'subProcess'): 'scope',              # 6.3.2: no loop characteristics

    # --- sequence flows ---
    (4, 'sequenceFlow'): 'sequence_flow',            # labelled branch off an exclusive decision
    (16, 'sequenceFlow'): 'sequence_flow',           # labelled branch off an inclusive decision

    # --- artifacts (no runtime behaviour) ---
    (21, 'dataObjectReference'): 'data_object_reference',   # 5.7/6.0 corpus
    (22, 'dataStoreReference'): 'data_store_reference',     # 5.7/6.0 corpus
    (22, 'dataObjectReference'): 'data_object_reference',   # 6.3.2
    (23, 'dataStoreReference'): 'data_store_reference',     # both
}

# ElementParameters entries with no diagram element.
ELEMENTLESS_TYPES = {18: 'unhandled_error_subprocess', 19: 'test_task'}

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
    'intermediateCatchEvent': 'catch',
    'callActivity': 'call_subprocess',
    'businessRuleTask': 'shared_state_task',
}

# Every documented shape has a known (Type, element) pair; an unknown Type is
# reported loudly.
NOT_IN_CORPUS = []

# Throw and Intermediate Return used to be listed here as indistinguishable.
# In 6.3.2 they are different elements and Types (6 vs 17). Nothing is
# ambiguous by Type; Assign Variable vs Code Task is resolved in classify().
AMBIGUOUS = {}
