#!/usr/bin/env python3
"""Generate a Frends-style .bpmn (with full DI) from a layout-free spec.

The caller never supplies coordinates. The model is expressed in Frends
vocabulary -- trigger, task, assign_variable, code_task, decision,
inclusive_decision, return, throw, foreach, while, scope, call_subprocess,
shared_state_task, catch -- with nesting as a parent reference.

IMPORTANT: this produces a DIAGRAM, not an importable Process. A Frends Process
needs a process.json carrying ElementParameters, GraphJson and TriggersJson, and
the actual functionality lives in ElementParameters, not in the BPMN XML.
For an importable Process use `python3 -m frendsgen generate`, which drives
build_layout() below from its own node list and emits both representations.
"""
import io
import json
import os
import sys

BPMN_NS = 'http://www.omg.org/spec/BPMN/20100524/MODEL'

# name -> (bpmn element, (w, h), extra child element or None)
# Sizes measured from the corpus at 100% share and cross-checked against the
# bpmn.io starter diagram and a Camunda Modeler file.
SHAPE = {
    'trigger':            ('startEvent',             (36, 36), None),
    'scope_trigger':      ('startEvent',             (36, 36), None),
    'return':             ('endEvent',               (36, 36), None),
    # Throw and Intermediate Return are the same element and both are terminal.
    'throw':              ('intermediateThrowEvent', (36, 36), 'signalEventDefinition'),
    'intermediate_return': ('intermediateThrowEvent', (36, 36), 'signalEventDefinition'),
    'task':               ('task',                   (100, 80), None),
    'code_task':          ('scriptTask',             (100, 80), None),
    'assign_variable':    ('scriptTask',             (30, 30), None),
    'shared_state_task':  ('businessRuleTask',       (100, 80), None),
    'call_subprocess':    ('callActivity',           (100, 80), None),
    'dmn_task':           ('businessRuleTask',       (100, 80), None),
    'ai_connector':       ('task',                   (100, 80), None),
    'decision':           ('exclusiveGateway',       (50, 50), None),
    'inclusive_decision': ('inclusiveGateway',       (50, 50), None),
    # Containers: size is computed from content, the tuple is a minimum.
    'scope':              ('subProcess',             (240, 160), None),
    'foreach':            ('subProcess',             (240, 160), 'multiInstanceLoopCharacteristics'),
    'while':              ('subProcess',             (240, 160), 'standardLoopCharacteristics'),
    # Doc-derived, NOT corpus-confirmed: Catch attaches to a Task or Scope, so it
    # must be a boundaryEvent. Its ElementParameters.Type is unknown.
    'catch':              ('boundaryEvent',          (36, 36), 'errorEventDefinition'),
}
CONTAINER_SHAPES = {'scope', 'foreach', 'while'}
GATEWAY_SHAPES = {'decision', 'inclusive_decision'}
TERMINAL_SHAPES = {'throw', 'intermediate_return', 'return'}

GAP = 60          # horizontal gap between columns
V_GAP = 60        # base vertical gap between row bands, before label allowance
LINE_H = 13.0     # rendered label line height
MAX_LABEL_LINES = 4
WRAP_CHARS = 22

# Which shapes carry their label BELOW the box and which carry it ABOVE.
# Small-shape labels go above: below, they collide with a neighbouring event's
# label. Events keep their labels below, matching the corpus.
LABEL_BELOW = {'trigger', 'scope_trigger', 'return', 'throw',
               'intermediate_return', 'catch'}
LABEL_ABOVE = {'decision', 'inclusive_decision', 'assign_variable'}
PAD_X = 40        # container padding left/right
PAD_TOP = 46      # container padding above content (room for the name)
PAD_BOTTOM = 30
EPS = 0.5


class GenError(Exception):
    pass


def elem_of(shape):
    if shape not in SHAPE:
        raise GenError('unknown shape %r; add it to SHAPE, to the extractor '
                       'Type map and to the validator tables' % shape)
    return SHAPE[shape]


# --------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------

def label_lines(text):
    if not text:
        return 0
    words, lines, cur = text.split(), 0, ''
    for w in words:
        cand = (cur + ' ' + w).strip()
        if len(cand) <= WRAP_CHARS:
            cur = cand
        else:
            lines += 1
            cur = w
    if cur:
        lines += 1
    return min(lines, MAX_LABEL_LINES)


def blocked(p, q, rects):
    x0, x1 = sorted((p[0], q[0]))
    y0, y1 = sorted((p[1], q[1]))
    for r in rects:
        if (x0 < r['x'] + r['w'] - EPS and x1 > r['x'] + EPS
                and y0 < r['y'] + r['h'] - EPS and y1 > r['y'] + EPS):
            return True
    return False


def simplify(wps):
    """Drop duplicate and collinear waypoints."""
    out = []
    for w in wps:
        if not out or abs(w[0] - out[-1][0]) > EPS or abs(w[1] - out[-1][1]) > EPS:
            out.append(w)
    i = 1
    while i < len(out) - 1:
        a, b, c = out[i - 1], out[i], out[i + 1]
        if (abs(a[0] - b[0]) < EPS and abs(b[0] - c[0]) < EPS) or \
           (abs(a[1] - b[1]) < EPS and abs(b[1] - c[1]) < EPS):
            del out[i]
        else:
            i += 1
    return out


def route_blocked(wps, rects):
    return any(blocked(p, q, rects) for p, q in zip(wps, wps[1:]))


def n_crossings(wps, rects):
    return sum(1 for p, q in zip(wps, wps[1:]) if blocked(p, q, rects))


# --------------------------------------------------------------------------
# layout of one nesting level
# --------------------------------------------------------------------------

def layout_level(node_ids, nodes, flows, sizes):
    """Place one nesting level. Returns {id: {x,y,w,h}} in local coordinates,
    plus the column table needed for routing."""
    idset = set(node_ids)
    succ = {n: [] for n in node_ids}
    pred = {n: [] for n in node_ids}
    for f in flows:
        if f['source'] in idset and f['target'] in idset:
            succ[f['source']].append(f['target'])
            pred[f['target']].append(f['source'])

    # boundary events (Catch) are not laid out on the grid; they are docked to
    # the shape they are attached to, after that shape has a position.
    attached = {n: nodes[n].get('attached_to') for n in node_ids
                if nodes[n]['shape'] == 'catch'}

    # Terminal events that dangle off a decision branch are not laid out on the
    # grid: Frends hangs them directly under the shape that branches to them.
    # Measured, not assumed -- 98.3% of Throw shapes in the corpus are entered
    # on their TOP edge, i.e. they sit below the row rather than in it. Leaving
    # them on the grid opens a whole band per Throw, and a tall container in
    # band 0 then pushes those bands hundreds of pixels down.
    hanging = {}
    for n in node_ids:
        if n in attached or nodes[n]['shape'] not in TERMINAL_SHAPES:
            continue
        if succ[n] or len(pred[n]) != 1:
            continue
        host = pred[n][0]
        if nodes[host]['shape'] in GATEWAY_SHAPES:
            hanging[n] = host
    grid = [n for n in node_ids if n not in attached and n not in hanging]

    # --- rank: longest path from a source ---
    # A Catch is off-grid (docked to the shape it guards), so its successors
    # would otherwise look like roots and rank 0 -- putting the error handler
    # to the LEFT of the Scope it guards. Treat a flow leaving a Catch as
    # leaving the shape the Catch is attached to.
    def rank_source(n):
        return attached.get(n) or n

    rank = {n: 0 for n in grid}
    for _ in range(len(grid) + 1):
        changed = False
        for n in grid:
            for s in succ[n]:
                if s in rank and rank[s] < rank[n] + 1:
                    rank[s] = rank[n] + 1
                    changed = True
        for c, host in attached.items():
            if host not in rank:
                continue
            for s in succ.get(c, []):
                if s in rank and rank[s] < rank[host] + 1:
                    rank[s] = rank[host] + 1
                    changed = True
        if not changed:
            break

    # downstream size, so a gateway's main branch is processed first and keeps
    # the straight line
    def downstream(n, seen=None):
        seen = seen or set()
        if n in seen:
            return 0
        seen.add(n)
        return 1 + sum(downstream(s, seen) for s in succ[n])

    dsz = {n: downstream(n) for n in grid}
    order = sorted(grid, key=lambda n: (rank[n], -dsz[n], str(nodes[n]['id'])))

    # --- rows: a node inherits its single predecessor's row; only extra
    #     branches open new rows. This is what keeps the main path straight;
    #     centring each column independently would bend it.
    #
    #     A branch that cannot inherit reuses the lowest existing band that is
    #     free across the whole span it reaches back over, and only opens a new
    #     band when none is. Always opening a new band is correct but sprawls:
    #     on a 45-node process it produced ten bands and a container that was
    #     half empty, where the original Frends file used four.
    row, claimed, occupied = {}, set(), set()

    def span_free(r, a, b):
        lo, hi = min(a, b), max(a, b)
        return all((k, r) not in occupied for k in range(lo, hi + 1))

    for n in order:
        ps = [p for p in pred[n] if p in row]
        cand = None
        for p in sorted(ps, key=lambda p: rank[p]):
            if p not in claimed and (rank[n], row[p]) not in occupied:
                cand = p
                break
        if cand is None:
            for p in sorted(ps, key=lambda p: row[p]):
                if (rank[n], row[p]) not in occupied:
                    cand = p
                    break
        if cand is not None:
            row[n] = row[cand]
            claimed.add(cand)
        elif row:
            back = min([rank[p] for p in ps], default=rank[n])
            # never reuse band 0: that is the main path's band
            reuse = [r for r in sorted(set(row.values()))
                     if r != 0 and span_free(r, back, rank[n])]
            row[n] = reuse[0] if reuse else max(row.values()) + 1
        else:
            row[n] = 0
        occupied.add((rank[n], row[n]))

    # --- columns: cumulative from the widest shape in each rank plus a fixed
    #     gap, so gaps stay constant across mixed widths.
    ranks = sorted(set(rank.values())) if grid else []
    col_w = {r: max([sizes[n][0] for n in grid if rank[n] == r] or [0])
             for r in ranks}
    col_x, x = {}, 0.0
    for r in ranks:
        col_x[r] = x
        x += col_w[r] + GAP

    rows = sorted(set(row.values())) if grid else []
    row_h = {k: max([sizes[n][1] for n in grid if row[n] == k] or [0])
             for k in rows}

    def below_lines(k):
        return max([label_lines(nodes[n].get('label')) for n in grid
                    if row[n] == k and nodes[n]['shape'] in LABEL_BELOW] or [0])

    def above_lines(k):
        return max([label_lines(nodes[n].get('label')) for n in grid
                    if row[n] == k and nodes[n]['shape'] in LABEL_ABOVE] or [0])

    # The gap between two bands must hold the lower edge labels of the upper band
    # and the upper edge labels of the lower band, or the two label blocks meet.
    row_cy, y = {}, 0.0
    for i, k in enumerate(rows):
        row_cy[k] = y + row_h[k] / 2.0
        if i + 1 < len(rows):
            gap = V_GAP + LINE_H * (below_lines(k) + above_lines(rows[i + 1]))
            y += row_h[k] + gap
    ctx_gap = V_GAP

    pos = {}
    for n in grid:
        w, h = sizes[n]
        # centred in the column, and centred on the row's centre line -- never
        # top-aligned. Top-aligning a small shape while docking its flows at the
        # row centre is the defect visible in a few shipped public templates.
        pos[n] = {'x': col_x[rank[n]] + (col_w[rank[n]] - w) / 2.0,
                  'y': row_cy[row[n]] - h / 2.0, 'w': w, 'h': h}

    # hang dangling terminals under the shape that branches to them, pushing
    # down until clear of everything already placed (labels included)
    def occupied_rect(nid):
        p = pos[nid]
        lines = label_lines(nodes[nid].get('label'))
        below = LINE_H * lines if nodes[nid]['shape'] in LABEL_BELOW else 0.0
        above = LINE_H * lines if nodes[nid]['shape'] in LABEL_ABOVE else 0.0
        return {'x': p['x'] - 8, 'y': p['y'] - above - 8,
                'w': p['w'] + 16, 'h': p['h'] + above + below + 16}

    by_host = {}
    for n, host in sorted(hanging.items(), key=lambda kv: str(kv[0])):
        by_host.setdefault(host, []).append(n)
    hang_slot = {n: i for ns in by_host.values() for i, n in enumerate(ns)}

    for n, host in sorted(hanging.items(), key=lambda kv: str(kv[0])):
        w, h = sizes[n]
        hp = pos[host]
        y = hp['y'] + hp['h'] + 70
        # Siblings sit SIDE BY SIDE, not stacked. Stacking them puts the second
        # Throw in the first one's vertical corridor, and the router then has to
        # take a six-waypoint detour over the top of the diagram to reach it.
        x = hp['x'] + hp['w'] / 2.0 - w / 2.0 + hang_slot[n] * (w + 70)
        lines = label_lines(nodes[n].get('label'))
        for _ in range(200):
            cand = {'x': x - 8, 'y': y - 8,
                    'w': w + 16, 'h': h + LINE_H * lines + 16}
            if not any(blocked((cand['x'], cand['y']),
                               (cand['x'] + cand['w'], cand['y'] + cand['h']),
                               [occupied_rect(o)]) for o in pos):
                break
            y += 30
        pos[n] = {'x': x, 'y': y, 'w': w, 'h': h}

    # dock Catch shapes on the bottom edge of the shape they guard
    for n, host in attached.items():
        w, h = sizes[n]
        if host not in pos:
            raise GenError('catch %s is attached to %s, which is not in the '
                           'same nesting level' % (n, host))
        hp = pos[host]
        pos[n] = {'x': hp['x'] + hp['w'] * 0.75 - w / 2.0,
                  'y': hp['y'] + hp['h'] - h / 2.0, 'w': w, 'h': h}

    ctx = {'col_x': col_x, 'col_w': col_w, 'rank': rank, 'row': row,
           'row_cy': row_cy, 'row_h': row_h, 'rows': rows}
    return pos, ctx


# --------------------------------------------------------------------------
# routing
# --------------------------------------------------------------------------

def corridors(ctx, from_cy):
    """Free horizontal corridors, nearest to the source row first.

    Never 'below every shape': a corridor below the bottom band would sit
    outside a container box if the box were sized before routing. We also size
    containers AFTER routing, so both halves of that bug are closed.
    """
    ys = []
    rows = ctx['rows']
    for a, b in zip(rows, rows[1:]):
        ys.append((ctx['row_cy'][a] + ctx['row_h'][a] / 2.0
                   + ctx['row_cy'][b] - ctx['row_h'][b] / 2.0) / 2.0)
    if rows:
        ys.append(ctx['row_cy'][rows[0]] - ctx['row_h'][rows[0]] / 2.0 - V_GAP / 2.0)
        ys.append(ctx['row_cy'][rows[-1]] + ctx['row_h'][rows[-1]] / 2.0 + V_GAP / 2.0)
    return sorted(ys, key=lambda y: abs(y - from_cy))


def gutter_right(ctx, n, p):
    # Off-grid shapes (hanging terminals, docked Catch events) have no column;
    # fall back to their own right edge.
    r = ctx['rank'].get(n)
    if r is None:
        return p['x'] + p['w'] + GAP / 2.0
    return ctx['col_x'][r] + ctx['col_w'][r] + GAP / 2.0


def gutter_left(ctx, n, p):
    # Measured from the COLUMN, not the shape. Offsetting from the target's own
    # left edge lands inside the column when a small shape is centred in a
    # column sized by a wider neighbour.
    r = ctx['rank'].get(n)
    if r is None:
        return p['x'] - GAP / 2.0
    return ctx['col_x'][r] - GAP / 2.0


def candidate_routes(s, t, ps, pt, ctx, is_gateway):
    scx, scy = ps['x'] + ps['w'] / 2.0, ps['y'] + ps['h'] / 2.0
    tcx, tcy = pt['x'] + pt['w'] / 2.0, pt['y'] + pt['h'] / 2.0
    r_mid = (ps['x'] + ps['w'], scy)
    l_mid = (pt['x'], tcy)
    same_row = abs(scy - tcy) < 1.0
    forward = pt['x'] >= ps['x'] + ps['w'] - EPS

    out = []
    # Directly below or above: a plain vertical drop, entering the target on its
    # TOP edge. This is what Frends draws for a Throw hanging off a decision --
    # 98.3% of Throw shapes in the corpus are entered on the top edge.
    if abs(scx - tcx) < 2.0:
        if pt['y'] >= ps['y'] + ps['h'] - EPS:
            out.append([(scx, ps['y'] + ps['h']), (tcx, pt['y'])])
        elif pt['y'] + pt['h'] <= ps['y'] + EPS:
            out.append([(scx, ps['y']), (tcx, pt['y'] + pt['h'])])
    if forward and same_row:
        out.append([r_mid, l_mid])
    if forward and not same_row:
        # gateway branch: leave vertically at the gateway's own centre-x, drop
        # to the target's centre-y, then into the target's left edge
        side_y = ps['y'] + ps['h'] if tcy > scy else ps['y']
        out.append([(scx, side_y), (scx, tcy), l_mid])
        # If that drop is blocked -- typically by the other branch's Throw
        # hanging directly under the gateway -- still leave on the vertical edge
        # and jog out to the gutter, rather than falling back to a right-edge
        # exit. Corpus house style is a vertical exit 96.6% of the time when the
        # target sits lower.
        jog = side_y + (20 if tcy > scy else -20)
        gxj = gutter_right(ctx, s, ps)
        out.append([(scx, side_y), (scx, jog), (gxj, jog), (gxj, tcy), l_mid])
        gx = gutter_right(ctx, s, ps)
        out.append([r_mid, (gx, scy), (gx, tcy), l_mid])
    if pt['y'] >= ps['y'] + ps['h'] + 20 and abs(scx - tcx) >= 2.0:
        # Bottom exit, jog across, drop into the target's TOP edge. Used for the
        # second and later Throws hanging off one decision.
        jy = ps['y'] + ps['h'] + 20
        out.append([(scx, ps['y'] + ps['h']), (scx, jy), (tcx, jy), (tcx, pt['y'])])
    if forward and same_row:
        # A long same-row hop draws straight through everything between when the
        # flow skips several ranks. Frends detours over the top and drops into
        # the target vertically: 4 waypoints, not a 6-waypoint gutter crawl.
        for cy in corridors(ctx, scy):
            if cy < scy:
                out.append([(scx, ps['y']), (scx, cy), (tcx, cy), (tcx, pt['y'])])
            else:
                out.append([(scx, ps['y'] + ps['h']), (scx, cy),
                            (tcx, cy), (tcx, pt['y'] + pt['h'])])
    if forward:
        gx1, gx2 = gutter_right(ctx, s, ps), gutter_left(ctx, t, pt)
        for cy in corridors(ctx, scy):
            out.append([r_mid, (gx1, scy), (gx1, cy), (gx2, cy), (gx2, tcy), l_mid])
    if not forward:
        # backward flow: drop below, run back, come up into the target
        for cy in corridors(ctx, scy):
            if cy <= scy:
                continue
            out.append([(scx, ps['y'] + ps['h']), (scx, cy),
                        (tcx, cy), (tcx, pt['y'] + pt['h'])])
        for cy in corridors(ctx, scy):
            if cy >= scy:
                continue
            out.append([(scx, ps['y']), (scx, cy), (tcx, cy), (tcx, pt['y'])])
        gx2 = gutter_left(ctx, t, pt)
        for cy in corridors(ctx, scy):
            out.append([r_mid, (gutter_right(ctx, s, ps), scy),
                        (gutter_right(ctx, s, ps), cy), (gx2, cy), (gx2, tcy), l_mid])
    if not out:
        out.append([r_mid, l_mid])
    return out


def route_all(level_flows, pos, ctx, obstacles_for):
    """Pick the first candidate route that clears every unrelated shape.

    Assume any route can be blocked. Four separate layout bugs were all this
    same mistake: trusting a route without checking it.
    """
    routes = {}
    for f in level_flows:
        s, t = f['source'], f['target']
        ps, pt = pos[s], pos[t]
        obst = obstacles_for(s, t)
        best, best_score = None, None
        for wps in candidate_routes(s, t, ps, pt, ctx, False):
            if not route_blocked(wps, obst):
                best = wps
                break
            score = (n_crossings(wps, obst), len(wps))
            if best_score is None or score < best_score:
                best, best_score = wps, score
        routes[f['id']] = simplify(best)
    return routes


# --------------------------------------------------------------------------
# whole-diagram layout
# --------------------------------------------------------------------------

def build_layout(spec):
    nodes = {n['id']: n for n in spec['nodes']}
    flows = spec['flows']

    for f in flows:
        for end in ('source', 'target'):
            if f[end] not in nodes:
                raise GenError('flow %s %s refers to unknown node %s'
                               % (f['id'], end, f[end]))
    # Frends never produces a flow whose two ends sit at different nesting
    # levels, and a silent drop would be invisible.
    for f in flows:
        ps, pt = nodes[f['source']].get('parent'), nodes[f['target']].get('parent')
        if ps != pt:
            raise GenError(
                'flow %s connects %s (in %s) to %s (in %s): its ends are at '
                'different nesting levels, which Frends never produces'
                % (f['id'], f['source'], ps or 'top level', f['target'],
                   pt or 'top level'))

    children = {}
    for n in spec['nodes']:
        children.setdefault(n.get('parent'), []).append(n['id'])

    pos, routes, ctxs = {}, {}, {}
    sizes = {}

    def do_level(parent):
        """Lay out one level, deepest containers first, and return its bbox."""
        ids = children.get(parent, [])
        for nid in ids:
            if nodes[nid]['shape'] in CONTAINER_SHAPES:
                inner = do_level(nid)
                sizes[nid] = (max(inner[0], SHAPE[nodes[nid]['shape']][1][0]),
                              max(inner[1], SHAPE[nodes[nid]['shape']][1][1]))
            else:
                sizes[nid] = SHAPE[nodes[nid]['shape']][1]

        lpos, ctx = layout_level(ids, nodes, flows, sizes)
        ctxs[parent] = ctx
        idset = set(ids)
        lflows = [f for f in flows
                  if f['source'] in idset and f['target'] in idset]

        # obstacles: sibling shapes only. Expanded containers legitimately
        # enclose other shapes, so a container is not an obstacle for flows
        # inside it -- but it IS one for its siblings.
        def obstacles_for(s, t):
            return [lpos[n] for n in ids if n not in (s, t)]

        lroutes = route_all(lflows, lpos, ctx, obstacles_for)

        # bbox over shapes AND waypoints, computed AFTER routing, so a fallback
        # corridor can never escape the container box.
        # The bbox must cover labels too, or a hanging Throw's four-line label
        # pokes out through the bottom edge of the container that holds it.
        def lab_top(nid):
            n = nodes[nid]
            if n['shape'] in LABEL_ABOVE:
                return LINE_H * label_lines(n.get('label')) + 6
            return 0.0

        def lab_bot(nid):
            n = nodes[nid]
            if n['shape'] in LABEL_BELOW:
                return LINE_H * label_lines(n.get('label')) + 6
            return 0.0

        xs = [p['x'] for p in lpos.values()] + \
             [w[0] for r in lroutes.values() for w in r]
        ys = [p['y'] - lab_top(k) for k, p in lpos.items()] + \
             [w[1] for r in lroutes.values() for w in r]
        xe = [p['x'] + p['w'] for p in lpos.values()] + \
             [w[0] for r in lroutes.values() for w in r]
        ye = [p['y'] + p['h'] + lab_bot(k) for k, p in lpos.items()] + \
             [w[1] for r in lroutes.values() for w in r]
        if not xs:
            bbox = (0.0, 0.0, 0.0, 0.0)
        else:
            bbox = (min(xs), min(ys), max(xe), max(ye))

        pos[parent] = lpos
        routes[parent] = lroutes
        return (bbox[2] - bbox[0] + 2 * PAD_X,
                bbox[3] - bbox[1] + PAD_TOP + PAD_BOTTOM,
                bbox[0], bbox[1])

    root_bbox = do_level(None)

    # translate every level into absolute coordinates, top down
    abs_pos, abs_routes = {}, {}

    def place(parent, ox, oy):
        lpos, lroutes = pos.get(parent, {}), routes.get(parent, {})
        if parent is None:
            bx, by = root_bbox[2], root_bbox[3]
            dx, dy = ox - bx + PAD_X, oy - by + PAD_TOP
        else:
            inner = level_bbox(lpos, lroutes)
            dx = abs_pos[parent]['x'] + PAD_X - inner[0]
            dy = abs_pos[parent]['y'] + PAD_TOP - inner[1]
        for nid, p in lpos.items():
            abs_pos[nid] = {'x': p['x'] + dx, 'y': p['y'] + dy,
                            'w': p['w'], 'h': p['h']}
        for fid, wps in lroutes.items():
            abs_routes[fid] = [(w[0] + dx, w[1] + dy) for w in wps]
        for nid in lpos:
            if nodes[nid]['shape'] in CONTAINER_SHAPES:
                place(nid, 0, 0)

    def level_bbox(lpos, lroutes):
        xs = [p['x'] for p in lpos.values()] + \
             [w[0] for r in lroutes.values() for w in r]
        ys = [p['y'] for p in lpos.values()] + \
             [w[1] for r in lroutes.values() for w in r]
        return (min(xs) if xs else 0.0, min(ys) if ys else 0.0)

    place(None, 0, 0)
    return nodes, abs_pos, abs_routes


# --------------------------------------------------------------------------
# XML emission
# --------------------------------------------------------------------------

def xesc(s):
    return (s or '').replace('&', '&amp;').replace('<', '&lt;') \
                    .replace('>', '&gt;').replace('"', '&quot;')


def emit(spec, nodes, pos, routes):
    children = {}
    for n in spec['nodes']:
        children.setdefault(n.get('parent'), []).append(n['id'])
    inc, outg = {}, {}
    for f in spec['flows']:
        outg.setdefault(f['source'], []).append(f['id'])
        inc.setdefault(f['target'], []).append(f['id'])
    flow_parent = {}
    for f in spec['flows']:
        flow_parent.setdefault(nodes[f['source']].get('parent'), []).append(f)

    o = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<bpmn2:definitions xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
         'xmlns:bpmn2="%s" '
         'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" '
         'xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" '
         'xmlns:di="http://www.omg.org/spec/DD/20100524/DI" id="sample-diagram" '
         'targetNamespace="http://bpmn.io/schema/bpmn" '
         'xsi:schemaLocation="http://www.omg.org/spec/BPMN/20100524/MODEL '
         'BPMN20.xsd">' % BPMN_NS]
    pid = spec.get('process_id') or 'Process_1'
    o.append('  <bpmn2:process id="%s" isExecutable="false">' % xesc(pid))

    def node_xml(nid, ind):
        n = nodes[nid]
        el, _size, extra = elem_of(n['shape'])
        pad = ' ' * ind
        attrs = ' id="%s"' % xesc(nid)
        if n.get('label'):
            attrs += ' name="%s"' % xesc(n['label'])
        if el == 'boundaryEvent':
            attrs += ' attachedToRef="%s"' % xesc(n['attached_to'])
        o.append('%s<bpmn2:%s%s>' % (pad, el, attrs))
        # incoming BEFORE outgoing
        for fid in inc.get(nid, []):
            o.append('%s  <bpmn2:incoming>%s</bpmn2:incoming>' % (pad, xesc(fid)))
        for fid in outg.get(nid, []):
            o.append('%s  <bpmn2:outgoing>%s</bpmn2:outgoing>' % (pad, xesc(fid)))
        # loopCharacteristics BEFORE the flow elements: it belongs to the base
        # tActivity type while flowElement is added by tSubProcess, and in an
        # XSD extension the base sequence comes first.
        if extra:
            o.append('%s  <bpmn2:%s id="%s_def"/>' % (pad, extra, xesc(nid)))
        if n['shape'] in CONTAINER_SHAPES:
            for cid in children.get(nid, []):
                node_xml(cid, ind + 2)
            for f in flow_parent.get(nid, []):
                flow_xml(f, ind + 2)
        o.append('%s</bpmn2:%s>' % (pad, el))

    def flow_xml(f, ind):
        pad = ' ' * ind
        a = ' id="%s" sourceRef="%s" targetRef="%s"' % (
            xesc(f['id']), xesc(f['source']), xesc(f['target']))
        if f.get('label'):
            a += ' name="%s"' % xesc(f['label'])
        o.append('%s<bpmn2:sequenceFlow%s/>' % (pad, a))

    for nid in children.get(None, []):
        node_xml(nid, 4)
    for f in flow_parent.get(None, []):
        flow_xml(f, 4)
    o.append('  </bpmn2:process>')

    o.append('  <bpmndi:BPMNDiagram id="BPMNDiagram_1">')
    o.append('    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="%s">' % xesc(pid))
    for nid, n in nodes.items():
        el, _s, _e = elem_of(n['shape'])
        p = pos[nid]
        extra = ''
        # isMarkerVisible on every exclusive gateway shape
        if el == 'exclusiveGateway':
            extra = ' isMarkerVisible="true"'
        if n['shape'] in CONTAINER_SHAPES:
            extra += ' isExpanded="true"'
        o.append('      <bpmndi:BPMNShape id="%s_di" bpmnElement="%s"%s>'
                 % (xesc(nid), xesc(nid), extra))
        o.append('        <dc:Bounds x="%.0f" y="%.0f" width="%.0f" height="%.0f"/>'
                 % (p['x'], p['y'], p['w'], p['h']))
        o.append('      </bpmndi:BPMNShape>')
    for f in spec['flows']:
        o.append('      <bpmndi:BPMNEdge id="%s_di" bpmnElement="%s">'
                 % (xesc(f['id']), xesc(f['id'])))
        for w in routes[f['id']]:
            o.append('        <di:waypoint x="%.0f" y="%.0f"/>' % (w[0], w[1]))
        o.append('      </bpmndi:BPMNEdge>')
    o.append('    </bpmndi:BPMNPlane>')
    o.append('  </bpmndi:BPMNDiagram>')
    o.append('</bpmn2:definitions>')
    return '\n'.join(o) + '\n'


def generate(spec):
    nodes, pos, routes = build_layout(spec)
    return emit(spec, nodes, pos, routes)


def main(argv):
    with io.open(argv[0], encoding='utf-8-sig') as fh:
        spec = json.load(fh)
    xml = generate(spec)
    with io.open(argv[1], 'w', encoding='utf-8') as fh:
        fh.write(xml)
    print('generated %s (%d nodes, %d flows)'
          % (argv[1], len(spec['nodes']), len(spec['flows'])))


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))


# BPMN element names this generator can emit; used by the round-trip harness to
# decide which elements in an original file are flow nodes it should compare.
SHAPE_ELEMENTS = {v[0] for v in SHAPE.values()}
