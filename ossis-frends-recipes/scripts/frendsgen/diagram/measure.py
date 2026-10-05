#!/usr/bin/env python3
"""Measure Frends drawing conventions from the untouched corpus.

Reports SHARES, not modes. "74% of gateway branches exit top or bottom" is a
different instruction from "gateway branches exit top or bottom", and the
difference decides whether a rule is an error or a warning in the validator.
"""
import io
import json
import os
import sys
from collections import defaultdict, Counter
from lxml import etree

BPMN = 'http://www.omg.org/spec/BPMN/20100524/MODEL'
BPMNDI = 'http://www.omg.org/spec/BPMN/20100524/DI'
DC = 'http://www.omg.org/spec/DD/20100524/DC'
DI = 'http://www.omg.org/spec/DD/20100524/DI'

CONTAINERS = {'subProcess', 'transaction', 'adHocSubProcess'}
GATEWAYS = {'exclusiveGateway', 'inclusiveGateway', 'parallelGateway',
            'complexGateway', 'eventBasedGateway'}
TOL = 3.0  # px tolerance when deciding "on the boundary" / "same centre line"


def ln(el):
    return etree.QName(el).localname


def parse(path):
    with io.open(path, encoding='utf-8-sig') as fh:
        return etree.fromstring(fh.read().encode('utf-8'))


def collect(root):
    """Return (shapes, edges, kinds, flows) for one file."""
    kinds, flows = {}, {}
    for el in root.iter():
        if not str(el.tag).startswith('{%s}' % BPMN):
            continue
        t = ln(el)
        if el.get('id'):
            kinds[el.get('id')] = t
        if t == 'sequenceFlow':
            flows[el.get('id')] = (el.get('sourceRef'), el.get('targetRef'))
    shapes = {}
    for sh in root.iter('{%s}BPMNShape' % BPMNDI):
        b = sh.find('{%s}Bounds' % DC)
        if b is None:
            continue
        shapes[sh.get('bpmnElement')] = {
            'x': float(b.get('x')), 'y': float(b.get('y')),
            'w': float(b.get('width')), 'h': float(b.get('height')),
            'marker': sh.get('isMarkerVisible'),
            'expanded': sh.get('isExpanded'),
        }
    edges = {}
    for ed in root.iter('{%s}BPMNEdge' % BPMNDI):
        wps = [(float(w.get('x')), float(w.get('y')))
               for w in ed.findall('{%s}waypoint' % DI)]
        edges[ed.get('bpmnElement')] = wps
    return shapes, edges, kinds, flows


def side_of(pt, s):
    """Which edge of shape s does point pt sit on?"""
    x, y = pt
    on_l = abs(x - s['x']) <= TOL
    on_r = abs(x - (s['x'] + s['w'])) <= TOL
    on_t = abs(y - s['y']) <= TOL
    on_b = abs(y - (s['y'] + s['h'])) <= TOL
    inside_y = s['y'] - TOL <= y <= s['y'] + s['h'] + TOL
    inside_x = s['x'] - TOL <= x <= s['x'] + s['w'] + TOL
    if on_l and inside_y:
        return 'left'
    if on_r and inside_y:
        return 'right'
    if on_t and inside_x:
        return 'top'
    if on_b and inside_x:
        return 'bottom'
    if inside_x and inside_y:
        return 'interior'
    return 'off-shape'


def pct(n, d):
    return '%5.1f%%' % (100.0 * n / d) if d else '  n/a'


def main(raw_dir):
    files = sorted(f for f in os.listdir(raw_dir) if f.endswith('.bpmn'))

    size = defaultdict(Counter)           # kind -> (w,h) -> n
    marker = defaultdict(Counter)         # gateway kind -> marker value -> n
    row_share = Counter()                 # kinds sharing a centre line
    row_mixed = Counter()
    gaps = Counter()
    wp_count = Counter()
    exit_side = defaultdict(Counter)      # source kind -> side -> n
    entry_side = defaultdict(Counter)     # target kind -> side -> n
    dy_bucket = Counter()
    io_counts = defaultdict(Counter)      # kind -> (in,out) -> n
    exit_by_dy = defaultdict(Counter)     # (source kind, samerow?) -> side
    boundary_ok = Counter()
    container_expanded = Counter()
    nesting_depth = Counter()
    label_pos = Counter()

    for fn in files:
        root = parse(os.path.join(raw_dir, fn))
        shapes, edges, kinds, flows = collect(root)

        for eid, s in shapes.items():
            k = kinds.get(eid, '?')
            if k in CONTAINERS:
                container_expanded[str(s['expanded'])] += 1
                continue          # container sizes are content-driven, not fixed
            size[k][(int(s['w']), int(s['h']))] += 1
            if k in GATEWAYS:
                marker[k][str(s['marker'])] += 1

        # vertical centre lines, per file, non-container shapes only
        rows = defaultdict(list)
        for eid, s in shapes.items():
            k = kinds.get(eid, '?')
            if k in CONTAINERS:
                continue
            rows[round((s['y'] + s['h'] / 2.0) / 2.0) * 2].append((s, k))
        for cy, members in rows.items():
            ks = sorted(set(k for _, k in members))
            if len(members) > 1:
                row_share[len(members)] += 1
                row_mixed[' + '.join(ks)] += 1
            members.sort(key=lambda m: m[0]['x'])
            for a, b in zip(members, members[1:]):
                g = b[0]['x'] - (a[0]['x'] + a[0]['w'])
                if g >= 0:
                    gaps[int(round(g / 5.0)) * 5] += 1

        # incoming/outgoing per kind
        ic, oc = Counter(), Counter()
        for src, tgt in flows.values():
            oc[src] += 1
            ic[tgt] += 1
        for eid, k in kinds.items():
            if eid in shapes and k not in ('sequenceFlow',):
                io_counts[k][(ic[eid], oc[eid])] += 1

        # per-flow routing
        for fid, (src, tgt) in flows.items():
            wps = edges.get(fid)
            if not wps or src not in shapes or tgt not in shapes:
                continue
            wp_count[len(wps)] += 1
            ss, ts = shapes[src], shapes[tgt]
            sk, tk = kinds.get(src, '?'), kinds.get(tgt, '?')
            es = side_of(wps[0], ss)
            en = side_of(wps[-1], ts)
            exit_side[sk][es] += 1
            entry_side[tk][en] += 1
            boundary_ok['first_on_source' if es not in ('off-shape', 'interior')
                        else 'first_OFF_source'] += 1
            boundary_ok['last_on_target' if en not in ('off-shape', 'interior')
                        else 'last_OFF_target'] += 1
            dy = (ts['y'] + ts['h'] / 2.0) - (ss['y'] + ss['h'] / 2.0)
            same = 'same-row' if abs(dy) <= TOL else (
                'down' if dy > 0 else 'up')
            dy_bucket[same] += 1
            exit_by_dy[(sk, same)][es] += 1

        # nesting depth
        def depth(el, d=0):
            nesting_depth[d] += 1
            for ch in el:
                if ln(ch) in CONTAINERS:
                    depth(ch, d + 1)
        proc = root.find('{%s}process' % BPMN)
        if proc is not None:
            for ch in proc:
                if ln(ch) in CONTAINERS:
                    depth(ch, 1)

        # label placement for small shapes: BPMNLabel bounds vs shape bounds
        for sh in root.iter('{%s}BPMNShape' % BPMNDI):
            lb = sh.find('{%s}BPMNLabel' % BPMNDI)
            b = sh.find('{%s}Bounds' % DC)
            if lb is None or b is None:
                continue
            lbb = lb.find('{%s}Bounds' % DC)
            if lbb is None:
                continue
            sy, sh_h = float(b.get('y')), float(b.get('height'))
            ly = float(lbb.get('y'))
            label_pos['above' if ly + 2 < sy else
                      ('below' if ly > sy + sh_h - 2 else 'overlap')] += 1

    out = []
    p = out.append
    p('files measured: %d\n' % len(files))

    p('=== shape size by BPMN element (non-container) ===')
    for k in sorted(size, key=lambda k: -sum(size[k].values())):
        tot = sum(size[k].values())
        items = ', '.join('%dx%d %s (n=%d)' % (w, h, pct(n, tot), n)
                          for (w, h), n in size[k].most_common(4))
        p('  %-24s n=%-4d %s' % (k, tot, items))

    p('\n=== container isExpanded ===')
    tot = sum(container_expanded.values())
    for v, n in container_expanded.most_common():
        p('  isExpanded=%-6s %s (n=%d)' % (v, pct(n, tot), n))

    p('\n=== isMarkerVisible on gateway shapes ===')
    for k, c in marker.items():
        tot = sum(c.values())
        for v, n in c.most_common():
            p('  %-20s isMarkerVisible=%-6s %s (n=%d)' % (k, v, pct(n, tot), n))

    p('\n=== nesting depth of containers ===')
    tot = sum(nesting_depth.values())
    for d, n in sorted(nesting_depth.items()):
        p('  depth %d  %s (n=%d)' % (d, pct(n, tot), n))

    p('\n=== shapes per shared vertical centre line ===')
    tot = sum(row_share.values())
    for n_members, n in sorted(row_share.items()):
        p('  %2d shapes on one centre line  %s (n=%d)' % (n_members, pct(n, tot), n))
    p('  most common kind combinations on a shared line:')
    for combo, n in row_mixed.most_common(6):
        p('    %-52s n=%d' % (combo[:52], n))

    p('\n=== horizontal gap between consecutive shapes on a row ===')
    tot = sum(gaps.values())
    for g, n in gaps.most_common(8):
        p('  gap %4d px  %s (n=%d)' % (g, pct(n, tot), n))

    p('\n=== waypoints per sequence flow ===')
    tot = sum(wp_count.values())
    for n_wp, n in sorted(wp_count.items()):
        p('  %d waypoints  %s (n=%d)' % (n_wp, pct(n, tot), n))

    p('\n=== vertical relationship of flow endpoints ===')
    tot = sum(dy_bucket.values())
    for k, n in dy_bucket.most_common():
        p('  %-10s %s (n=%d)' % (k, pct(n, tot), n))

    p('\n=== first/last waypoint on the shape boundary ===')
    for k in ('first_on_source', 'first_OFF_source', 'last_on_target', 'last_OFF_target'):
        d = boundary_ok['first_on_source'] + boundary_ok['first_OFF_source'] \
            if k.startswith('first') else \
            boundary_ok['last_on_target'] + boundary_ok['last_OFF_target']
        p('  %-18s %s (n=%d)' % (k, pct(boundary_ok[k], d), boundary_ok[k]))

    p('\n=== exit edge of source, by element kind ===')
    for k in sorted(exit_side, key=lambda k: -sum(exit_side[k].values())):
        tot = sum(exit_side[k].values())
        if tot < 5:
            continue
        p('  %-24s n=%-4d %s' % (k, tot, ', '.join(
            '%s %s' % (s, pct(n, tot)) for s, n in exit_side[k].most_common())))

    p('\n=== entry edge of target, by element kind ===')
    for k in sorted(entry_side, key=lambda k: -sum(entry_side[k].values())):
        tot = sum(entry_side[k].values())
        if tot < 5:
            continue
        p('  %-24s n=%-4d %s' % (k, tot, ', '.join(
            '%s %s' % (s, pct(n, tot)) for s, n in entry_side[k].most_common())))

    p('\n=== gateway exit edge, split by where the target sits ===')
    for (k, rel), c in sorted(exit_by_dy.items()):
        if k not in GATEWAYS:
            continue
        tot = sum(c.values())
        p('  %-18s target %-9s n=%-4d %s' % (k, rel, tot, ', '.join(
            '%s %s' % (s, pct(n, tot)) for s, n in c.most_common())))

    p('\n=== incoming/outgoing flow counts per element kind ===')
    for k in sorted(io_counts, key=lambda k: -sum(io_counts[k].values())):
        tot = sum(io_counts[k].values())
        p('  %-24s n=%-4d %s' % (k, tot, ', '.join(
            'in=%d out=%d %s' % (i, o, pct(n, tot))
            for (i, o), n in io_counts[k].most_common(4))))

    p('\n=== label box vertical placement relative to its shape ===')
    tot = sum(label_pos.values())
    for k, n in label_pos.most_common():
        p('  %-8s %s (n=%d)' % (k, pct(n, tot), n))

    txt = '\n'.join(out)
    print(txt)
    with io.open(os.path.join(os.path.dirname(raw_dir), 'measurements.txt'),
                 'w', encoding='utf-8') as fh:
        fh.write(txt + '\n')


if __name__ == '__main__':
    main(sys.argv[1])
