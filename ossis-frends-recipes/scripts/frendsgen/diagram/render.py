#!/usr/bin/env python3
"""Render a .bpmn to SVG from the layout already in its BPMNDI.

No re-layout: every coordinate comes from the file. That turns any Frends export
into a clean diagram for a blog post or a review, and it doubles as a check that
our reading of the DI matches what a real renderer would do -- if the picture is
wrong, either the DI is wrong or our reading of it is.
"""
import html
import io
import os
import sys
from lxml import etree

BPMN = 'http://www.omg.org/spec/BPMN/20100524/MODEL'
BPMNDI = 'http://www.omg.org/spec/BPMN/20100524/DI'
DC = 'http://www.omg.org/spec/DD/20100524/DC'
DI = 'http://www.omg.org/spec/DD/20100524/DI'

CONTAINERS = {'subProcess', 'transaction', 'adHocSubProcess'}
GATEWAYS = {'exclusiveGateway', 'inclusiveGateway', 'parallelGateway',
            'complexGateway', 'eventBasedGateway'}
EVENTS = {'startEvent', 'endEvent', 'intermediateThrowEvent',
          'intermediateCatchEvent', 'boundaryEvent'}
ACTIVITIES = {'task', 'serviceTask', 'scriptTask', 'businessRuleTask',
              'sendTask', 'receiveTask', 'userTask', 'manualTask',
              'callActivity'}

STROKE = '#3c4b5e'
FILL = '#ffffff'
CONTAINER_FILL = '#f7f9fb'
TEXT = '#1d2733'
ACCENT = '#4a90d9'


def ln(el):
    return etree.QName(el).localname


def esc(s):
    return html.escape(s or '', quote=True)


def wrap(text, width_chars):
    words, lines, cur = (text or '').split(), [], ''
    for w in words:
        cand = (cur + ' ' + w).strip()
        if len(cand) <= width_chars:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:4]


def parse(path):
    with io.open(path, encoding='utf-8-sig') as fh:
        return etree.fromstring(fh.read().encode('utf-8'))


def collect(root):
    kinds, names, loops, evdefs = {}, {}, {}, {}
    flows, flow_names = {}, {}
    annos, cats, assocs = {}, {}, {}
    catvals = {}
    for el in root.iter('{%s}categoryValue' % BPMN):
        catvals[el.get('id')] = el.get('value')
    for el in root.iter():
        if not str(el.tag).startswith('{%s}' % BPMN):
            continue
        t, eid = ln(el), el.get('id')
        if t == 'sequenceFlow':
            flows[eid] = (el.get('sourceRef'), el.get('targetRef'))
            if el.get('name'):
                flow_names[eid] = el.get('name')
            continue
        if t in ('association', 'dataInputAssociation', 'dataOutputAssociation'):
            assocs[eid] = True
            continue
        if t == 'textAnnotation':
            tx = el.find('{%s}text' % BPMN)
            annos[eid] = (tx.text if tx is not None else '') or ''
        if t == 'group' and el.get('categoryValueRef'):
            cats[eid] = catvals.get(el.get('categoryValueRef'), '')
        if eid:
            kinds[eid] = t
            if el.get('name'):
                names[eid] = el.get('name')
            for ch in el:
                ct = ln(ch)
                if ct.endswith('LoopCharacteristics'):
                    loops[eid] = ct
                elif ct.endswith('EventDefinition'):
                    evdefs[eid] = ct
    shapes, edges = {}, {}
    for sh in root.iter('{%s}BPMNShape' % BPMNDI):
        b = sh.find('{%s}Bounds' % DC)
        if b is None:
            continue
        shapes[sh.get('bpmnElement')] = {
            'x': float(b.get('x')), 'y': float(b.get('y')),
            'w': float(b.get('width')), 'h': float(b.get('height'))}
    for ed in root.iter('{%s}BPMNEdge' % BPMNDI):
        edges[ed.get('bpmnElement')] = [
            (float(w.get('x')), float(w.get('y')))
            for w in ed.findall('{%s}waypoint' % DI)]
    return (kinds, names, loops, evdefs, flows, flow_names, shapes,
            edges, annos, cats, assocs)


def render(path):
    root = parse(path)
    (kinds, names, loops, evdefs, flows, flow_names, shapes, edges,
     annos, cats, assocs) = collect(root)
    if not shapes:
        raise ValueError('no BPMNShape elements: nothing to draw')

    xs = [s['x'] for s in shapes.values()] + [p[0] for e in edges.values() for p in e]
    ys = [s['y'] for s in shapes.values()] + [p[1] for e in edges.values() for p in e]
    xe = [s['x'] + s['w'] for s in shapes.values()] + [p[0] for e in edges.values() for p in e]
    ye = [s['y'] + s['h'] for s in shapes.values()] + [p[1] for e in edges.values() for p in e]
    M = 40
    minx, miny, maxx, maxy = min(xs) - M, min(ys) - M, max(xe) + M, max(ye) + M
    W, H = maxx - minx, maxy - miny

    o = []
    o.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
             'viewBox="%.1f %.1f %.1f %.1f" font-family="IBM Plex Sans, '
             'Segoe UI, Helvetica, Arial, sans-serif">'
             % (int(W), int(H), minx, miny, W, H))
    o.append('<defs><marker id="a" markerWidth="10" markerHeight="8" refX="9" '
             'refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 z" fill="%s"/>'
             '</marker></defs>' % STROKE)
    o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="#ffffff"/>'
             % (minx, miny, W, H))

    # containers first, so their children draw on top
    def z(eid):
        k = kinds.get(eid)
        if k == 'group':
            return 0
        if k in CONTAINERS:
            return 1
        return 2
    order = sorted(shapes.items(),
                   key=lambda kv: (z(kv[0]), -kv[1]['w'] * kv[1]['h']))

    for eid, s in order:
        k = kinds.get(eid)
        x, y, w, h = s['x'], s['y'], s['w'], s['h']
        cx, cy = x + w / 2, y + h / 2
        label = names.get(eid, '')
        if k in CONTAINERS:
            o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="8" '
                     'fill="%s" stroke="%s" stroke-width="1.6"/>'
                     % (x, y, w, h, CONTAINER_FILL, STROKE))
            o.append('<text x="%.1f" y="%.1f" font-size="12" font-weight="600" '
                     'fill="%s">%s</text>' % (x + 10, y + 18, TEXT, esc(label)))
            if eid in loops:
                mk = '↻' if loops[eid].startswith('standard') else '≡'
                o.append('<text x="%.1f" y="%.1f" font-size="15" fill="%s" '
                         'text-anchor="middle">%s</text>'
                         % (cx, y + h - 6, STROKE, mk))
        elif k in EVENTS:
            sw = 3.0 if k == 'endEvent' else 1.6
            dash = ' stroke-dasharray="4 2"' if k == 'boundaryEvent' else ''
            o.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" stroke="%s" '
                     'stroke-width="%.1f"%s/>' % (cx, cy, w / 2, FILL, STROKE, sw, dash))
            if k == 'intermediateThrowEvent':
                o.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" '
                         'stroke="%s" stroke-width="1.2"/>' % (cx, cy, w / 2 - 3, STROKE))
                o.append('<path d="M%.1f,%.1f l4,-5 l-1,4 l4,0 l-6,7 l1,-5 l-4,0 z" '
                         'fill="%s"/>' % (cx - 4, cy + 2, STROKE))
            elif k in ('intermediateCatchEvent', 'boundaryEvent'):
                o.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" '
                         'stroke="%s" stroke-width="1.2"/>' % (cx, cy, w / 2 - 3, STROKE))
                o.append('<path d="M%.1f,%.1f l3,6 l4,-9 l3,7" fill="none" '
                         'stroke="%s" stroke-width="1.4"/>' % (cx - 6, cy - 1, STROKE))
            for i, line in enumerate(wrap(label, 22)):
                o.append('<text x="%.1f" y="%.1f" font-size="10.5" fill="%s" '
                         'text-anchor="middle">%s</text>'
                         % (cx, y + h + 13 + i * 12, TEXT, esc(line)))
        elif k in GATEWAYS:
            o.append('<path d="M%.1f,%.1f L%.1f,%.1f L%.1f,%.1f L%.1f,%.1f z" '
                     'fill="%s" stroke="%s" stroke-width="1.6"/>'
                     % (cx, y, x + w, cy, cx, y + h, x, cy, FILL, STROKE))
            if k == 'exclusiveGateway':
                d = w * 0.22
                o.append('<path d="M%.1f,%.1f L%.1f,%.1f M%.1f,%.1f L%.1f,%.1f" '
                         'stroke="%s" stroke-width="2" fill="none"/>'
                         % (cx - d, cy - d, cx + d, cy + d, cx + d, cy - d,
                            cx - d, cy + d, STROKE))
            elif k == 'inclusiveGateway':
                o.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" '
                         'stroke="%s" stroke-width="2"/>' % (cx, cy, w * 0.26, STROKE))
            for i, line in enumerate(wrap(label, 24)):
                o.append('<text x="%.1f" y="%.1f" font-size="10.5" fill="%s" '
                         'text-anchor="middle">%s</text>'
                         % (cx, y - 8 - (len(wrap(label, 24)) - 1 - i) * 12, TEXT,
                            esc(line)))
        elif k == 'group':
            o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="10" '
                     'fill="none" stroke="%s" stroke-width="1.3" '
                     'stroke-dasharray="10 4 2 4" opacity="0.55"/>'
                     % (x, y, w, h, STROKE))
            gl = label or cats.get(eid, '')
            if gl:
                o.append('<text x="%.1f" y="%.1f" font-size="11" font-weight="600" '
                         'fill="%s" opacity="0.7">%s</text>'
                         % (x + 10, y - 6, TEXT, esc(gl)))
        elif k == 'textAnnotation':
            o.append('<path d="M%.1f,%.1f L%.1f,%.1f L%.1f,%.1f" fill="none" '
                     'stroke="%s" stroke-width="1.3" opacity="0.75"/>'
                     % (x + 10, y, x, y, x, y + h, STROKE))
            o.append('<path d="M%.1f,%.1f L%.1f,%.1f" fill="none" stroke="%s" '
                     'stroke-width="1.3" opacity="0.75"/>'
                     % (x, y + h, x + 10, y + h, STROKE))
            for i, line in enumerate(wrap(annos.get(eid, ''), 24)):
                o.append('<text x="%.1f" y="%.1f" font-size="10" fill="%s" '
                         'opacity="0.85">%s</text>'
                         % (x + 6, y + 13 + i * 12, TEXT, esc(line)))
        elif k in ('dataObjectReference', 'dataObject'):
            fold = 10
            o.append('<path d="M%.1f,%.1f h%.1f l%.1f,%.1f v%.1f h%.1f z" '
                     'fill="%s" stroke="%s" stroke-width="1.4"/>'
                     % (x, y, w - fold, fold, fold, h - fold, -w, FILL, STROKE))
            o.append('<path d="M%.1f,%.1f v%.1f h%.1f" fill="none" stroke="%s" '
                     'stroke-width="1.2"/>' % (x + w - fold, y, fold, fold, STROKE))
            for i, line in enumerate(wrap(label, 18)):
                o.append('<text x="%.1f" y="%.1f" font-size="10" fill="%s" '
                         'text-anchor="middle">%s</text>'
                         % (cx, y + h + 12 + i * 11, TEXT, esc(line)))
        elif k == 'dataStoreReference':
            ry = h * 0.16
            o.append('<path d="M%.1f,%.1f v%.1f a%.1f,%.1f 0 0 0 %.1f,0 v%.1f '
                     'a%.1f,%.1f 0 0 0 %.1f,0 z" fill="%s" stroke="%s" '
                     'stroke-width="1.4"/>'
                     % (x, y + ry, h - 2 * ry, w / 2, ry, w, -(h - 2 * ry),
                        w / 2, ry, -w, FILL, STROKE))
            o.append('<path d="M%.1f,%.1f a%.1f,%.1f 0 0 0 %.1f,0" fill="none" '
                     'stroke="%s" stroke-width="1.2"/>'
                     % (x, y + ry, w / 2, ry, w, STROKE))
            for i, line in enumerate(wrap(label, 18)):
                o.append('<text x="%.1f" y="%.1f" font-size="10" fill="%s" '
                         'text-anchor="middle">%s</text>'
                         % (cx, y + h + 12 + i * 11, TEXT, esc(line)))
        else:
            small = w < 60
            o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" '
                     'fill="%s" stroke="%s" stroke-width="1.6"/>'
                     % (x, y, w, h, 6 if not small else 4, FILL, STROKE))
            if k == 'scriptTask':
                o.append('<path d="M%.1f,%.1f h8 M%.1f,%.1f h8 M%.1f,%.1f h5" '
                         'stroke="%s" stroke-width="1.2" fill="none"/>'
                         % (x + 5, y + 8, x + 5, y + 12, x + 5, y + 16, STROKE))
            elif k == 'businessRuleTask':
                o.append('<rect x="%.1f" y="%.1f" width="12" height="9" fill="none" '
                         'stroke="%s" stroke-width="1.2"/>' % (x + 5, y + 6, STROKE))
            elif k == 'callActivity':
                o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="6" '
                         'fill="none" stroke="%s" stroke-width="2.4"/>'
                         % (x + 2, y + 2, w - 4, h - 4, STROKE))
            if small:
                # Small-shape labels go ABOVE: below they collide with a
                # neighbouring event's label.
                lines = wrap(label, 20)
                for i, line in enumerate(lines):
                    o.append('<text x="%.1f" y="%.1f" font-size="10.5" fill="%s" '
                             'text-anchor="middle">%s</text>'
                             % (cx, y - 6 - (len(lines) - 1 - i) * 12, TEXT, esc(line)))
            else:
                lines = wrap(label, 16)
                y0 = cy - (len(lines) - 1) * 6.5
                for i, line in enumerate(lines):
                    o.append('<text x="%.1f" y="%.1f" font-size="11" fill="%s" '
                             'text-anchor="middle">%s</text>'
                             % (cx, y0 + i * 13 + 4, TEXT, esc(line)))

    for fid, wps in edges.items():
        if len(wps) < 2:
            continue
        d = 'M%.1f,%.1f ' % wps[0] + ' '.join('L%.1f,%.1f' % p for p in wps[1:])
        if fid in assocs:
            o.append('<path d="%s" fill="none" stroke="%s" stroke-width="1.2" '
                     'stroke-dasharray="4 3" opacity="0.6"/>' % (d, STROKE))
            continue
        o.append('<path d="%s" fill="none" stroke="%s" stroke-width="1.5" '
                 'marker-end="url(#a)"/>' % (d, STROKE))
        nm = flow_names.get(fid)
        if nm:
            # Longest segment, offset off the line. Anchoring to the first
            # segment drops the label on top of a gateway's own label whenever
            # the flow leaves vertically.
            segs = list(zip(wps, wps[1:]))
            a, b = max(segs, key=lambda s: abs(s[1][0] - s[0][0])
                       + abs(s[1][1] - s[0][1]))
            lx, ly = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            if abs(b[0] - a[0]) >= abs(b[1] - a[1]):
                o.append('<text x="%.1f" y="%.1f" font-size="10" fill="%s" '
                         'text-anchor="middle">%s</text>'
                         % (lx, ly - 6, ACCENT, esc(nm)))
            else:
                o.append('<text x="%.1f" y="%.1f" font-size="10" fill="%s" '
                         'text-anchor="start">%s</text>'
                         % (lx + 5, ly, ACCENT, esc(nm)))

    o.append('</svg>')
    return '\n'.join(o)


def main(argv):
    src, dst = argv[0], argv[1]
    if os.path.isdir(src):
        os.makedirs(dst, exist_ok=True)
        n = 0
        for fn in sorted(os.listdir(src)):
            if not fn.endswith('.bpmn'):
                continue
            try:
                svg = render(os.path.join(src, fn))
            except Exception as exc:
                print('  ! %s: %s' % (fn, exc))
                continue
            with io.open(os.path.join(dst, fn[:-5] + '.svg'), 'w',
                         encoding='utf-8') as fh:
                fh.write(svg)
            n += 1
        print('rendered %d file(s) to %s' % (n, dst))
    else:
        svg = render(src)
        with io.open(dst, 'w', encoding='utf-8') as fh:
            fh.write(svg)
        print('rendered %s' % dst)


if __name__ == '__main__':
    main(sys.argv[1:])
