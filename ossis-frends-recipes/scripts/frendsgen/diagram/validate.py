#!/usr/bin/env python3
"""Validate a Frends-style .bpmn file.

Two severities:
  ERROR   -- broken, or will render wrong in bpmn.io
  WARNING -- Frends house style, derived from corpus shares below 100%

Every rule was calibrated by running this over the 77 untouched corpus files
first. A rule that fired on shipped Frends Processes was either wrong or moved
to warning severity. See CALIBRATION.md for what that changed.
"""
import io
import os
import sys
from lxml import etree

BPMN = 'http://www.omg.org/spec/BPMN/20100524/MODEL'
BPMNDI = 'http://www.omg.org/spec/BPMN/20100524/DI'
DC = 'http://www.omg.org/spec/DD/20100524/DC'
DI = 'http://www.omg.org/spec/DD/20100524/DI'

TOL = 3.0

# A validator that does not know subProcess reports the entire corpus as broken.
CONTAINERS = {'subProcess', 'transaction', 'adHocSubProcess'}
GATEWAYS = {'exclusiveGateway', 'inclusiveGateway', 'parallelGateway',
            'complexGateway', 'eventBasedGateway'}
FLOW_NODES = {
    'task', 'serviceTask', 'scriptTask', 'businessRuleTask', 'sendTask',
    'receiveTask', 'userTask', 'manualTask', 'callActivity',
    'startEvent', 'endEvent', 'intermediateThrowEvent',
    'intermediateCatchEvent', 'boundaryEvent',
} | CONTAINERS | GATEWAYS

ARTIFACTS = {'textAnnotation', 'group', 'dataObjectReference',
             'dataStoreReference', 'dataObject'}

# Sizes measured at 100% share in the corpus AND confirmed against the bpmn.io
# starter diagram and a Camunda Modeler file, so they are BPMN convention.
STD_SIZE = {
    'task': (100, 80),
    'serviceTask': (100, 80),
    'businessRuleTask': (100, 80),
    'userTask': (100, 80),
    'startEvent': (36, 36),
    'endEvent': (36, 36),
    'intermediateThrowEvent': (36, 36),
    'intermediateCatchEvent': (36, 36),
    'boundaryEvent': (36, 36),
    'exclusiveGateway': (50, 50),
    'inclusiveGateway': (50, 50),
}
# scriptTask is legitimately either 30x30 (Assign Variable) or 100x80 (Code Task).
ALT_SIZE = {'scriptTask': [(30, 30), (100, 80)]}

# The XSD ordering trap. Inside a subProcess, loopCharacteristics belongs to the
# base tActivity type while flowElement is added by tSubProcess, and in an XSD
# extension the base sequence comes first -- so loopCharacteristics must precede
# the flow elements. Getting it backwards renders fine and passes any
# geometry-only validator.
LOOP_TAGS = {'multiInstanceLoopCharacteristics', 'standardLoopCharacteristics'}
IO_SPEC = {'ioSpecification'}
PROPERTY = {'property'}


def ln(el):
    return etree.QName(el).localname


class Report:
    def __init__(self, path):
        self.path = path
        self.errors = []
        self.warnings = []

    def err(self, rule, msg):
        self.errors.append((rule, msg))

    def warn(self, rule, msg):
        self.warnings.append((rule, msg))

    @property
    def ok(self):
        return not self.errors


def rects_overlap(a, b):
    return not (a['x'] + a['w'] <= b['x'] + TOL or b['x'] + b['w'] <= a['x'] + TOL
                or a['y'] + a['h'] <= b['y'] + TOL or b['y'] + b['h'] <= a['y'] + TOL)


def seg_crosses_rect(p, q, r):
    """Does segment p-q pass through rectangle r? Axis-aligned segments only."""
    x0, x1 = sorted((p[0], q[0]))
    y0, y1 = sorted((p[1], q[1]))
    rx0, ry0 = r['x'] + TOL, r['y'] + TOL
    rx1, ry1 = r['x'] + r['w'] - TOL, r['y'] + r['h'] - TOL
    return x0 < rx1 and x1 > rx0 and y0 < ry1 and y1 > ry0


def on_boundary(pt, s):
    x, y = pt
    within_y = s['y'] - TOL <= y <= s['y'] + s['h'] + TOL
    within_x = s['x'] - TOL <= x <= s['x'] + s['w'] + TOL
    return ((abs(x - s['x']) <= TOL or abs(x - (s['x'] + s['w'])) <= TOL) and within_y) \
        or ((abs(y - s['y']) <= TOL or abs(y - (s['y'] + s['h'])) <= TOL) and within_x)


def side_of(pt, s):
    x, y = pt
    within_y = s['y'] - TOL <= y <= s['y'] + s['h'] + TOL
    within_x = s['x'] - TOL <= x <= s['x'] + s['w'] + TOL
    if abs(x - s['x']) <= TOL and within_y:
        return 'left'
    if abs(x - (s['x'] + s['w'])) <= TOL and within_y:
        return 'right'
    if abs(y - s['y']) <= TOL and within_x:
        return 'top'
    if abs(y - (s['y'] + s['h'])) <= TOL and within_x:
        return 'bottom'
    return 'off'


def validate(path):
    rep = Report(path)
    try:
        with io.open(path, encoding='utf-8-sig') as fh:
            root = etree.fromstring(fh.read().encode('utf-8'))
    except Exception as exc:
        rep.err('parse', 'cannot parse: %s' % exc)
        return rep

    proc = root.find('{%s}process' % BPMN)
    if proc is None:
        rep.err('structure', 'no bpmn:process element')
        return rep

    kinds, parent = {}, {}
    flows = {}
    declared_in, declared_out = {}, {}

    def scan(container, pid):
        for el in container:
            t = ln(el)
            eid = el.get('id')
            if t == 'sequenceFlow':
                flows[eid] = (el.get('sourceRef'), el.get('targetRef'))
                continue
            if t in FLOW_NODES:
                kinds[eid] = t
                parent[eid] = pid
                declared_in[eid] = [c.text for c in
                                    el.findall('{%s}incoming' % BPMN)]
                declared_out[eid] = [c.text for c in
                                     el.findall('{%s}outgoing' % BPMN)]
                if t in CONTAINERS:
                    check_child_order(el, eid, rep)
                    scan(el, eid)
            elif t in ARTIFACTS:
                kinds[eid] = t
                parent[eid] = pid

    scan(proc, None)

    # --- DI ---
    shapes, edges = {}, {}
    for sh in root.iter('{%s}BPMNShape' % BPMNDI):
        b = sh.find('{%s}Bounds' % DC)
        if b is None:
            rep.err('di', 'BPMNShape %s has no Bounds' % sh.get('id'))
            continue
        shapes[sh.get('bpmnElement')] = {
            'x': float(b.get('x')), 'y': float(b.get('y')),
            'w': float(b.get('width')), 'h': float(b.get('height')),
            'marker': sh.get('isMarkerVisible'),
        }
    for ed in root.iter('{%s}BPMNEdge' % BPMNDI):
        edges[ed.get('bpmnElement')] = [
            (float(w.get('x')), float(w.get('y')))
            for w in ed.findall('{%s}waypoint' % DI)]

    # --- ERROR: dangling refs ---
    for fid, (s, t) in flows.items():
        if s not in kinds:
            rep.err('dangling-ref', 'flow %s sourceRef %s does not exist' % (fid, s))
        if t not in kinds:
            rep.err('dangling-ref', 'flow %s targetRef %s does not exist' % (fid, t))

    # --- ERROR: incoming/outgoing lists disagree with the actual flows ---
    actual_in, actual_out = {}, {}
    for fid, (s, t) in flows.items():
        actual_out.setdefault(s, []).append(fid)
        actual_in.setdefault(t, []).append(fid)
    for eid in kinds:
        if kinds[eid] in ARTIFACTS:
            continue
        if sorted(declared_in.get(eid) or []) != sorted(actual_in.get(eid, [])):
            rep.err('io-mismatch', '%s declares incoming %s but flows say %s'
                    % (eid, sorted(declared_in.get(eid) or []),
                       sorted(actual_in.get(eid, []))))
        if sorted(declared_out.get(eid) or []) != sorted(actual_out.get(eid, [])):
            rep.err('io-mismatch', '%s declares outgoing %s but flows say %s'
                    % (eid, sorted(declared_out.get(eid) or []),
                       sorted(actual_out.get(eid, []))))

    # --- ERROR: missing DI ---
    for eid, k in kinds.items():
        if k in ARTIFACTS:
            continue
        if eid not in shapes:
            rep.err('missing-di', '%s %s has no BPMNShape' % (k, eid))
    for fid in flows:
        if fid not in edges:
            rep.err('missing-di', 'flow %s has no BPMNEdge' % fid)

    # --- ERROR: exclusive gateway missing isMarkerVisible ---
    # Calibrated: 286/286 exclusiveGateway shapes carry it, but the single
    # inclusiveGateway in the corpus does NOT. Scoping this to exclusiveGateway
    # is what stops the rule firing on a shipped file.
    for eid, k in kinds.items():
        if k == 'exclusiveGateway' and eid in shapes:
            if shapes[eid]['marker'] != 'true':
                rep.err('gateway-marker',
                        'exclusiveGateway %s missing isMarkerVisible="true"' % eid)
        elif k in GATEWAYS and k != 'exclusiveGateway' and eid in shapes:
            if shapes[eid]['marker'] != 'true':
                rep.warn('gateway-marker',
                         '%s %s has no isMarkerVisible (matches corpus, but '
                         'bpmn.io draws no marker)' % (k, eid))

    # --- ERROR: waypoint off its shape boundary ---
    for fid, (s, t) in flows.items():
        wps = edges.get(fid)
        if not wps or len(wps) < 2:
            if wps is not None and len(wps) < 2:
                rep.err('waypoints', 'flow %s has %d waypoints' % (fid, len(wps)))
            continue
        if s in shapes and not on_boundary(wps[0], shapes[s]):
            rep.err('waypoint-off-shape',
                    'flow %s first waypoint %s is not on source %s boundary'
                    % (fid, wps[0], s))
        if t in shapes and not on_boundary(wps[-1], shapes[t]):
            rep.err('waypoint-off-shape',
                    'flow %s last waypoint %s is not on target %s boundary'
                    % (fid, wps[-1], t))

    # --- ERROR: overlapping shapes ---
    # Expanded containers legitimately enclose other shapes, so they are excluded
    # from overlap and edge-crossing checks -- otherwise every nested process fails.
    solid = {eid: s for eid, s in shapes.items()
             if kinds.get(eid) not in CONTAINERS and kinds.get(eid) not in ARTIFACTS
             and eid in kinds}
    ids = sorted(solid)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if rects_overlap(solid[a], solid[b]):
                rep.err('overlap', 'shapes %s and %s overlap' % (a, b))

    # --- ERROR: edge segment crossing an unrelated shape ---
    for fid, (s, t) in flows.items():
        wps = edges.get(fid) or []
        for p, q in zip(wps, wps[1:]):
            for eid, sh in solid.items():
                if eid in (s, t):
                    continue
                if seg_crosses_rect(p, q, sh):
                    rep.err('edge-crossing',
                            'flow %s crosses shape %s' % (fid, eid))

    # --- WARNING: non-standard shape size ---
    for eid, k in kinds.items():
        if eid not in shapes or k in CONTAINERS or k in ARTIFACTS:
            continue
        w, h = int(shapes[eid]['w']), int(shapes[eid]['h'])
        if k in STD_SIZE and (w, h) != STD_SIZE[k]:
            rep.warn('shape-size', '%s %s is %dx%d, corpus standard is %dx%d'
                     % (k, eid, w, h, *STD_SIZE[k]))
        elif k in ALT_SIZE and (w, h) not in ALT_SIZE[k]:
            rep.warn('shape-size', '%s %s is %dx%d, corpus uses %s'
                     % (k, eid, w, h, ALT_SIZE[k]))

    # --- WARNING: gateway branch leaving on an unexpected edge ---
    # Corpus: target below -> bottom 96.6%; same row -> right 98.8%;
    # target above -> top 70.8%. All house style, none universal.
    for fid, (s, t) in flows.items():
        wps = edges.get(fid)
        if not wps or s not in shapes or t not in shapes:
            continue
        if kinds.get(s) not in GATEWAYS:
            continue
        ss, ts = shapes[s], shapes[t]
        dy = (ts['y'] + ts['h'] / 2) - (ss['y'] + ss['h'] / 2)
        side = side_of(wps[0], ss)
        want = 'right' if abs(dy) <= TOL else ('bottom' if dy > 0 else 'top')
        if side != want:
            rep.warn('gateway-exit',
                     'flow %s leaves %s on %s; corpus house style is %s'
                     % (fid, s, side, want))

    # --- WARNING: straight same-row hop drawn with extra waypoints ---
    for fid, (s, t) in flows.items():
        wps = edges.get(fid)
        if not wps or s not in shapes or t not in shapes:
            continue
        ss, ts = shapes[s], shapes[t]
        same_row = abs((ts['y'] + ts['h'] / 2) - (ss['y'] + ss['h'] / 2)) <= TOL
        forward = ts['x'] >= ss['x'] + ss['w'] - TOL
        if same_row and forward and len(wps) > 2:
            # Calibrated: only a detour that was not NEEDED is house-style noise.
            # A same-row hop skipping several ranks must go around the shapes in
            # between, and the naive rule flagged those legitimate detours -- 4
            # times on the untouched corpus.
            direct = [(ss['x'] + ss['w'], ss['y'] + ss['h'] / 2),
                      (ts['x'], ts['y'] + ts['h'] / 2)]
            others = [sh for eid, sh in solid.items() if eid not in (s, t)]
            if not any(seg_crosses_rect(direct[0], direct[1], r) for r in others):
                rep.warn('extra-waypoints',
                         'flow %s is a straight same-row hop with a clear direct '
                         'line but has %d waypoints' % (fid, len(wps)))

    # --- WARNING: main path bends ---
    # A node with a single predecessor should sit on its predecessor's centre line.
    #
    # Calibrated. The naive form fired 94 times across 41 of 77 shipped files,
    # because two of its firings are not bends at all:
    #   * containers are sized by their content, so a subProcess centre line
    #     legitimately differs from its predecessor's (40 firings);
    #   * Return and Throw shapes deliberately hang below the row and are entered
    #     from the top -- 43.8% of endEvents and 98.3% of throws in the corpus
    #     (40 firings).
    # Restricting the rule to flows that actually enter the target's LEFT edge,
    # i.e. intended horizontal continuations, leaves 14 genuine firings.
    preds = {}
    for fid, (s, t) in flows.items():
        preds.setdefault(t, []).append((s, fid))
    for eid, ps in preds.items():
        if len(ps) != 1 or eid not in shapes:
            continue
        p, fid = ps[0]
        if p not in shapes or kinds.get(p) in GATEWAYS or parent.get(p) != parent.get(eid):
            continue
        if len(actual_out.get(p, [])) != 1:
            continue
        if kinds.get(p) in CONTAINERS or kinds.get(eid) in CONTAINERS:
            continue
        wps = edges.get(fid)
        if not wps or side_of(wps[-1], shapes[eid]) != 'left':
            continue
        cy_a = shapes[p]['y'] + shapes[p]['h'] / 2
        cy_b = shapes[eid]['y'] + shapes[eid]['h'] / 2
        if abs(cy_a - cy_b) > TOL:
            rep.warn('main-path-bend',
                     '%s is the only successor of %s but sits %.0f px off its '
                     'centre line' % (eid, p, cy_b - cy_a))

    # --- cardinality, from docs + corpus ---
    for eid, k in kinds.items():
        n_in = len(actual_in.get(eid, []))
        n_out = len(actual_out.get(eid, []))
        if k == 'exclusiveGateway' and n_out != 2:
            rep.err('cardinality',
                    'exclusiveGateway %s has %d outgoing flows; docs require '
                    'exactly two branches' % (eid, n_out))
        if k in ('task', 'serviceTask', 'businessRuleTask') and n_out > 2:
            rep.warn('cardinality', '%s %s has %d outgoing flows; docs say one, '
                     'plus optionally an Intermediate Return or Catch'
                     % (k, eid, n_out))
        if k == 'intermediateThrowEvent' and n_out != 0:
            rep.err('cardinality',
                    'Throw / Intermediate Return %s has %d outgoing flows; both '
                    'are terminal in the XML' % (eid, n_out))
        if k in CONTAINERS:
            inner_starts = [c for c in
                            root.xpath('//*[@id=$i]', i=eid)[0]
                            if ln(c) == 'startEvent']
            if len(inner_starts) != 1:
                rep.err('scope-trigger',
                        'container %s holds %d Trigger shapes; docs require '
                        'exactly one' % (eid, len(inner_starts)))

    return rep


def check_child_order(el, eid, rep):
    """XSD ordering inside a subProcess: loopCharacteristics before flow elements."""
    seen_flow = False
    for ch in el:
        t = ln(ch)
        if t in ('incoming', 'outgoing', 'extensionElements'):
            continue
        if t in LOOP_TAGS or t in IO_SPEC or t in PROPERTY:
            if seen_flow:
                rep.err('child-order',
                        'subProcess %s puts <%s> after its flow elements; the XSD '
                        'requires it before (tActivity base sequence precedes the '
                        'tSubProcess extension)' % (eid, t))
        else:
            seen_flow = True


def main(argv):
    paths = []
    for a in argv:
        if os.path.isdir(a):
            paths += [os.path.join(a, f) for f in sorted(os.listdir(a))
                      if f.endswith('.bpmn')]
        else:
            paths.append(a)

    n_err_files = 0
    err_rules, warn_rules = {}, {}
    for p in paths:
        rep = validate(p)
        if rep.errors:
            n_err_files += 1
        for r, m in rep.errors:
            err_rules.setdefault(r, []).append((p, m))
        for r, m in rep.warnings:
            warn_rules.setdefault(r, []).append((p, m))

    print('validated %d file(s): %d clean, %d with errors'
          % (len(paths), len(paths) - n_err_files, n_err_files))
    if err_rules:
        print('\nERRORS by rule:')
        for r, items in sorted(err_rules.items(), key=lambda kv: -len(kv[1])):
            print('  %-22s %d occurrence(s) in %d file(s)'
                  % (r, len(items), len(set(i[0] for i in items))))
            for p, m in items[:3]:
                print('      %s: %s' % (os.path.basename(p)[:44], m[:110]))
    if warn_rules:
        print('\nWARNINGS by rule:')
        for r, items in sorted(warn_rules.items(), key=lambda kv: -len(kv[1])):
            print('  %-22s %d occurrence(s) in %d file(s)'
                  % (r, len(items), len(set(i[0] for i in items))))
            for p, m in items[:2]:
                print('      %s: %s' % (os.path.basename(p)[:44], m[:110]))
    return 1 if n_err_files else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
