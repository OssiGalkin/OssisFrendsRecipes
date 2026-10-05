#!/usr/bin/env python3
"""Round-trip every extracted spec through the generator.

Checks three things:
  1. does the generator accept the spec
  2. do node ids / element kinds / flow pairs / nesting match the original
  3. does the validator pass

Be honest about what each proves. Check 2 is WEAK: the spec stores exactly those
fields verbatim, so a pass mostly proves nothing was dropped. What the round-trip
genuinely exercises is the layout engine, against processes far messier than
anything you would hand-author.
"""
import io
import json
import os
import sys

from . import generate
from . import validate
from lxml import etree

BPMN = 'http://www.omg.org/spec/BPMN/20100524/MODEL'


def ln(el):
    return etree.QName(el).localname


def structure_of(path):
    with io.open(path, encoding='utf-8-sig') as fh:
        root = etree.fromstring(fh.read().encode('utf-8'))
    proc = root.find('{%s}process' % BPMN)
    nodes, flows = {}, set()

    def walk(container, parent):
        for el in container:
            t, eid = ln(el), el.get('id')
            if t == 'sequenceFlow':
                flows.add((eid, el.get('sourceRef'), el.get('targetRef')))
            elif t in generate.SHAPE_ELEMENTS:
                nodes[eid] = (t, parent)
                if t in ('subProcess', 'transaction', 'adHocSubProcess'):
                    walk(el, eid)
    walk(proc, None)
    return nodes, flows


def main(spec_dir, raw_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    specs = sorted(f for f in os.listdir(spec_dir) if f.endswith('.json'))

    gen_fail, struct_fail, val_fail, ok = [], [], [], 0
    err_rules, warn_rules = {}, {}

    for fn in specs:
        slug = fn[:-5]
        with io.open(os.path.join(spec_dir, fn), encoding='utf-8-sig') as fh:
            spec = json.load(fh)
        out_path = os.path.join(out_dir, slug + '.bpmn')

        try:
            xml = generate.generate(spec)
        except Exception as exc:
            gen_fail.append((slug, '%s: %s' % (type(exc).__name__, exc)))
            continue
        with io.open(out_path, 'w', encoding='utf-8') as fh:
            fh.write(xml)

        try:
            got_n, got_f = structure_of(out_path)
            want_n, want_f = structure_of(os.path.join(raw_dir, slug + '.bpmn'))
        except Exception as exc:
            struct_fail.append((slug, 'compare: %s' % exc))
            continue

        problems = []
        if set(got_n) != set(want_n):
            missing = sorted(set(want_n) - set(got_n))[:3]
            extra = sorted(set(got_n) - set(want_n))[:3]
            problems.append('node ids differ (missing %s, extra %s)'
                            % (missing, extra))
        else:
            for nid in want_n:
                if got_n[nid][0] != want_n[nid][0]:
                    problems.append('%s kind %s != %s'
                                    % (nid, got_n[nid][0], want_n[nid][0]))
                if got_n[nid][1] != want_n[nid][1]:
                    problems.append('%s parent %s != %s'
                                    % (nid, got_n[nid][1], want_n[nid][1]))
        if got_f != want_f:
            d = sorted(want_f - got_f)[:2] + sorted(got_f - want_f)[:2]
            problems.append('flow set differs, e.g. %s' % (d,))
        if problems:
            struct_fail.append((slug, '; '.join(problems[:3])))
            continue

        rep = validate.validate(out_path)
        for r, m in rep.errors:
            err_rules.setdefault(r, []).append((slug, m))
        for r, m in rep.warnings:
            warn_rules.setdefault(r, []).append((slug, m))
        if rep.errors:
            val_fail.append((slug, '%d error(s)' % len(rep.errors)))
        else:
            ok += 1

    n = len(specs)
    print('round-trip over %d spec(s)' % n)
    print('  generator accepted : %d' % (n - len(gen_fail)))
    print('  structure matched  : %d   (weak check: the spec stores these '
          'fields verbatim)' % (n - len(gen_fail) - len(struct_fail)))
    print('  validator clean    : %d' % ok)
    for title, items in (('GENERATOR FAILURES', gen_fail),
                         ('STRUCTURE MISMATCHES', struct_fail),
                         ('VALIDATION FAILURES', val_fail)):
        if items:
            print('\n%s (%d):' % (title, len(items)))
            for slug, msg in items[:8]:
                print('  %-46s %s' % (slug[:46], msg[:110]))
    if err_rules:
        print('\nerrors by rule:')
        for r, items in sorted(err_rules.items(), key=lambda kv: -len(kv[1])):
            print('  %-22s %d in %d file(s)'
                  % (r, len(items), len(set(i[0] for i in items))))
            for slug, m in items[:2]:
                print('      %s: %s' % (slug[:40], m[:100]))
    if warn_rules:
        print('\nwarnings by rule:')
        for r, items in sorted(warn_rules.items(), key=lambda kv: -len(kv[1])):
            print('  %-22s %d in %d file(s)'
                  % (r, len(items), len(set(i[0] for i in items))))
    return 0 if (ok == n) else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
