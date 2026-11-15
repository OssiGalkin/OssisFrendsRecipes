# Non-Frends cross-references

## bpmn.io starter (bpmn-io/bpmn-js-examples, starter/diagram.bpmn)
Fetched via CDN mirror (cdn.statically.io/gh/...); github.com /blob/ HTML was blocked by fetch policy.

- task 100x80, startEvent/endEvent 36x36, exclusiveGateway 50x50 -> identical to Frends.
  => These sizes are bpmn.io/BPMN convention, NOT Frends house style.
- isMarkerVisible="true" on both exclusiveGateways -> also bpmn.io convention.
- Backward flow (Yes branch looping back): 4 waypoints, leaves source gateway BOTTOM,
  runs along a corridor below the row, re-enters the target gateway BOTTOM.
  => "backward flow drops below and comes back up" is bpmn.io convention too.
- Namespace prefixes differ (omgdc/omgdi vs dc/di). Prefix choice is free; namespace URI is what matters.
- Uses collaboration + participant + laneSet. Frends never does: one bare <process>.

## Camunda Modeler (camunda/camunda-bpm-examples, servicetask/rest-service/invokeRestService.bpmn)
Fetched from github.com /blob/ (allowed; /raw/ and /tree/ are blocked for automated fetch).

- startEvent/endEvent 36x36, task/userTask/serviceTask 100x80, exclusiveGateway 50x50,
  isMarkerVisible="true". Identical to Frends and to bpmn.io.
- Gateway branch to another row: 3 waypoints, leaves the gateway TOP (y=196) or BOTTOM
  (y=246) at the gateway's own centre-x (431), drops to the target's centre-y, then runs
  into the target's LEFT edge. Identical to the Frends convention measured in the corpus.
- Same-row hop: 2 waypoints, source right edge -> target left edge.
- Horizontal gap is a uniform 50 px (206->256, 356->406, 456->506, 606->656).

## Conclusion: what is BPMN convention vs what is Frends house style

BPMN / modeller convention (all three sources agree, so NOT a Frends signature):
  - the shape sizes 36x36 / 50x50 / 100x80
  - isMarkerVisible="true" on exclusive gateways
  - 2-waypoint same-row hop, right edge -> left edge
  - 3-waypoint gateway branch leaving vertically at the gateway's centre-x
  - backward flows routed through a corridor below the row

Frends house style (only the Frends corpus does this):
  - Assign Variable drawn as a 30x30 square, a size neither reference uses at all
  - Throw events entered from the TOP, 98.3% of the time: error throws hang below the
    main row rather than sitting in it
  - gateway branch direction is asymmetric: 96.6% BOTTOM when the target is lower,
    but only 70.8% TOP when the target is higher (Camunda splits top/bottom evenly)
  - heavy container nesting (61 containers over 77 files, 19.7% of them at depth 2);
    neither reference nests at all
  - one bare <process>, never collaboration/participant/laneSet
  - horizontal gap is NOT fixed: 55/65/75/60 px are all common (Camunda uses a uniform 50)
