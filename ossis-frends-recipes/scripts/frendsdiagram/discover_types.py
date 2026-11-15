#!/usr/bin/env python3
"""Correlate ElementParameters[].Type with the BPMN element carrying the same id.

That correlation is the only way to learn which Frends shape is which BPMN
element. Also reports DI width per (Type, element) so shapes that share a Type
can be told apart, and the event-definition child, which distinguishes
Throw/Intermediate Return from other intermediate events.
"""
import io
import json
import os
import sys
from collections import defaultdict
from lxml import etree

BPMN = 'http://www.omg.org/spec/BPMN/20100524/MODEL'
BPMNDI = 'http://www.omg.org/spec/BPMN/20100524/DI'
DC = 'http://www.omg.org/spec/DD/20100524/DC'


def ln(el):
    return etree.QName(el).localname


def walk(node, out):
    if isinstance(node, dict):
        b = node.get('Bpmn')
        if isinstance(b, str) and b.strip():
            out.append(node)
        for v in node.values():
            walk(v, out)
    elif isinstance(node, list):
        for v in node:
            walk(v, out)


def ep_list(proc):
    ep = proc.get('ElementParameters')
    if isinstance(ep, str):
        try:
            ep = json.loads(ep) if ep.strip() else []
        except json.JSONDecodeError:
            return []
    return ep if isinstance(ep, list) else []


def main(corpus):
    agg = defaultdict(lambda: {'n': 0, 'sel': defaultdict(int),
                               'labels': [], 'w': defaultdict(int),
                               'h': defaultdict(int), 'evdef': defaultdict(int),
                               'names': defaultdict(int)})
    no_ep = defaultdict(int)
    files = []
    for dp, _, fns in os.walk(corpus):
        for fn in fns:
            if fn.lower().endswith('.json'):
                files.append(os.path.join(dp, fn))

    for path in sorted(files):
        try:
            with io.open(path, encoding='utf-8-sig') as fh:
                data = json.load(fh)
        except Exception:
            continue
        procs = []
        walk(data, procs)
        for proc in procs:
            try:
                root = etree.fromstring(proc['Bpmn'].encode('utf-8'))
            except Exception:
                continue
            by_id = {e.get('id'): e for e in root.iter() if e.get('id')}
            bounds = {}
            for sh in root.iter('{%s}BPMNShape' % BPMNDI):
                bd = sh.find('{%s}Bounds' % DC)
                if bd is not None:
                    bounds[sh.get('bpmnElement')] = (
                        int(float(bd.get('width'))), int(float(bd.get('height'))))
            ids_with_ep = set()
            for e in ep_list(proc):
                if not isinstance(e, dict):
                    continue
                eid = e.get('Id')
                ids_with_ep.add(eid)
                el = by_id.get(eid)
                if el is None:
                    continue
                tag = ln(el)
                rec = agg[(e.get('Type'), tag)]
                rec['n'] += 1
                rec['sel'][str(e.get('SelectedTypeId'))[:60]] += 1
                nm = el.get('name') or e.get('Name')
                if nm and len(rec['labels']) < 12:
                    rec['labels'].append(nm)
                if eid in bounds:
                    rec['w'][bounds[eid][0]] += 1
                    rec['h'][bounds[eid][1]] += 1
                for ch in el:
                    if ln(ch).endswith('EventDefinition'):
                        rec['evdef'][ln(ch)] += 1
                rec['names'][tag] += 1
            # elements with no ElementParameters entry at all
            for el in root.iter():
                if not str(el.tag).startswith('{%s}' % BPMN):
                    continue
                t = ln(el)
                if t in ('definitions', 'process', 'extensionElements'):
                    continue
                if el.get('id') and el.get('id') not in ids_with_ep:
                    no_ep[t] += 1

    print('=== (ElementParameters.Type, BPMN element) correlation ===\n')
    for (t, tag), r in sorted(agg.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
        print('Type=%-5s %-24s n=%-4d' % (t, tag, r['n']))
        print('    widths : %s' % dict(sorted(r['w'].items())))
        print('    heights: %s' % dict(sorted(r['h'].items())))
        if r['evdef']:
            print('    evdef  : %s' % dict(r['evdef']))
        sel = sorted(r['sel'].items(), key=lambda kv: -kv[1])[:6]
        print('    selIds : %s' % sel)
        print('    labels : %s' % r['labels'][:6])
        print()

    print('=== elements with NO ElementParameters entry ===')
    for t, n in sorted(no_ep.items(), key=lambda kv: -kv[1]):
        print('  %-28s %d' % (t, n))


if __name__ == '__main__':
    main(sys.argv[1])
