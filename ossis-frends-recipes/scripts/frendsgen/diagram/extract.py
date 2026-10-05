#!/usr/bin/env python3
"""Extract every Frends Process from a corpus of export JSON files.

Writes, per process:
  raw/<slug>.bpmn   the raw Bpmn field, verbatim
  spec/<slug>.json  a layout-free structural spec

Wrapper keys differ by export kind (Templates nest under
ProcessTemplates[]->ProcessInfo->Process, Process exports use Processes[],
Subprocess exports differ again), so we do not key on any of them: we walk the
JSON depth-first for any object carrying a non-empty `Bpmn` field.
"""
import io
import json
import os
import re
import sys
from lxml import etree

from .shapes import TYPE_TO_SHAPE, BPMN_FALLBACK_SHAPE

NS = {
    'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
    'bpmndi': 'http://www.omg.org/spec/BPMN/20100524/DI',
    'dc': 'http://www.omg.org/spec/DD/20100524/DC',
    'di': 'http://www.omg.org/spec/DD/20100524/DI',
}

FLOW_NODE_TAGS = {
    'task', 'serviceTask', 'scriptTask', 'businessRuleTask', 'sendTask',
    'receiveTask', 'userTask', 'manualTask', 'callActivity', 'subProcess',
    'transaction', 'adHocSubProcess',
    'startEvent', 'endEvent', 'intermediateThrowEvent',
    'intermediateCatchEvent', 'boundaryEvent',
    'exclusiveGateway', 'inclusiveGateway', 'parallelGateway',
    'complexGateway', 'eventBasedGateway',
}

# Artifacts and data elements the layout-free spec deliberately drops.
DROPPED_TAGS = {
    'textAnnotation', 'group', 'association', 'dataObject',
    'dataObjectReference', 'dataStoreReference', 'dataInputAssociation',
    'dataOutputAssociation', 'dataInput', 'dataOutput',
}


def localname(el):
    return etree.QName(el).localname


def slugify(s):
    s = re.sub(r'[^A-Za-z0-9]+', '_', s or 'process').strip('_')
    return (s or 'process')[:90]


def walk_for_processes(node, out):
    """Depth-first walk for any dict with a non-empty Bpmn field."""
    if isinstance(node, dict):
        b = node.get('Bpmn')
        if isinstance(b, str) and b.strip():
            out.append(node)
        for v in node.values():
            walk_for_processes(v, out)
    elif isinstance(node, list):
        for v in node:
            walk_for_processes(v, out)


def load_element_parameters(proc):
    """ElementParameters may arrive as a JSON string rather than a list."""
    ep = proc.get('ElementParameters')
    if ep is None:
        return []
    if isinstance(ep, str):
        ep = ep.strip()
        if not ep:
            return []
        try:
            ep = json.loads(ep)
        except json.JSONDecodeError:
            return []
    return ep if isinstance(ep, list) else []


def di_bounds(root):
    """id -> (x, y, w, h) from BPMNDI, used only to discriminate shapes that
    share an ElementParameters Type (Assign Variable vs Code Task)."""
    out = {}
    for sh in root.iter('{%s}BPMNShape' % NS['bpmndi']):
        ref = sh.get('bpmnElement')
        bd = sh.find('{%s}Bounds' % NS['dc'])
        if ref is not None and bd is not None:
            out[ref] = (float(bd.get('x')), float(bd.get('y')),
                        float(bd.get('w' 'idth')), float(bd.get('height')))
    return out


def classify(elem_id, tag, ep_type, selected_type_id, bounds, unknowns, label):
    """Resolve a Frends shape name.

    The Type -> shape correlation is the only way to learn which Frends shape a
    BPMN element is drawn as; the docs name the types but not their elements. Three Types mislead and are
    handled explicitly (see notes.md).
    """
    if ep_type is not None:
        key = (ep_type, tag)
        # Assign Variable and Code Task share Type 12; both are scriptTask.
        # The only discriminator is DI width.
        if ep_type == 12 and tag == 'scriptTask':
            w = bounds.get(elem_id, (0, 0, 0, 0))[2]
            return 'assign_variable' if w and w < 60 else 'code_task'
        if key in TYPE_TO_SHAPE:
            return TYPE_TO_SHAPE[key]
        if (ep_type, None) in TYPE_TO_SHAPE:
            return TYPE_TO_SHAPE[(ep_type, None)]
        unknowns.append({
            'type': ep_type, 'bpmn_element': tag,
            'selected_type_id': selected_type_id, 'label': label,
            'id': elem_id,
        })
        return 'UNKNOWN_TYPE_%s' % ep_type
    # No ElementParameters entry. Normal for unlabelled sequence flows; for
    # flow nodes fall back on the BPMN element itself.
    return BPMN_FALLBACK_SHAPE.get(tag, 'UNKNOWN_ELEMENT_%s' % tag)


def extract_spec(bpmn_xml, element_parameters, name):
    root = etree.fromstring(bpmn_xml.encode('utf-8'))
    bounds = di_bounds(root)

    ep_by_id = {}
    for e in element_parameters:
        if isinstance(e, dict) and e.get('Id'):
            ep_by_id[e['Id']] = e

    unknowns = []
    nodes, flows, dropped = [], [], []

    proc_el = root.find('{%s}process' % NS['bpmn'])
    if proc_el is None:
        raise ValueError('no bpmn:process element')

    def visit(container, parent_id):
        for el in container:
            tag = localname(el)
            eid = el.get('id')
            if tag in DROPPED_TAGS:
                dropped.append({'kind': tag, 'id': eid})
                continue
            if tag == 'sequenceFlow':
                ep = ep_by_id.get(eid)
                flows.append({
                    'id': eid,
                    'source': el.get('sourceRef'),
                    'target': el.get('targetRef'),
                    'label': el.get('name') or (ep or {}).get('Name') or None,
                })
                continue
            if tag not in FLOW_NODE_TAGS:
                continue
            ep = ep_by_id.get(eid) or {}
            shape = classify(eid, tag, ep.get('Type'),
                             ep.get('SelectedTypeId'), bounds, unknowns,
                             el.get('name') or ep.get('Name'))
            rec = {
                'id': eid,
                'shape': shape,
                'label': el.get('name') or ep.get('Name') or None,
                'parent': parent_id,
                'bpmn_element': tag,
            }
            if tag == 'boundaryEvent':
                rec['attached_to'] = el.get('attachedToRef')
            if el.find('{%s}multiInstanceLoopCharacteristics' % NS['bpmn']) is not None:
                rec['loop'] = 'multiInstance'
            elif el.find('{%s}standardLoopCharacteristics' % NS['bpmn']) is not None:
                rec['loop'] = 'standard'
            nodes.append(rec)
            if tag in ('subProcess', 'transaction', 'adHocSubProcess'):
                visit(el, eid)

    visit(proc_el, None)

    return {
        'name': name,
        'process_id': proc_el.get('id'),
        'is_executable': proc_el.get('isExecutable'),
        'nodes': nodes,
        'flows': flows,
        'dropped_artifacts': dropped,
    }, unknowns


def main(corpus_dir, out_dir):
    raw_dir = os.path.join(out_dir, 'raw')
    spec_dir = os.path.join(out_dir, 'spec')
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(spec_dir, exist_ok=True)

    json_files = []
    for dp, _, fns in os.walk(corpus_dir):
        for fn in fns:
            if fn.lower().endswith('.json'):
                json_files.append(os.path.join(dp, fn))

    index, all_unknowns, errors = [], [], []
    seen = set()
    for path in sorted(json_files):
        try:
            # Files carry a UTF-8 BOM; utf-8-sig or parsing raises.
            with io.open(path, encoding='utf-8-sig') as fh:
                data = json.load(fh)
        except Exception as exc:
            errors.append({'file': path, 'error': 'load: %s' % exc})
            continue
        procs = []
        walk_for_processes(data, procs)
        for proc in procs:
            name = proc.get('Name') or os.path.basename(os.path.dirname(path))
            slug = slugify(name)
            n, base = 1, slug
            while slug in seen:
                n += 1
                slug = '%s__%d' % (base, n)
            seen.add(slug)
            try:
                spec, unknowns = extract_spec(
                    proc['Bpmn'], load_element_parameters(proc), name)
            except Exception as exc:
                errors.append({'file': path, 'name': name,
                               'error': '%s: %s' % (type(exc).__name__, exc)})
                continue
            with io.open(os.path.join(raw_dir, slug + '.bpmn'), 'w',
                         encoding='utf-8') as fh:
                fh.write(proc['Bpmn'])
            with io.open(os.path.join(spec_dir, slug + '.json'), 'w',
                         encoding='utf-8') as fh:
                json.dump(spec, fh, indent=2, ensure_ascii=False)
            for u in unknowns:
                u['process'] = name
            all_unknowns.extend(unknowns)
            index.append({
                'slug': slug, 'name': name, 'source': path,
                'is_subprocess': bool(proc.get('IsSubprocess')),
                'nodes': len(spec['nodes']), 'flows': len(spec['flows']),
                'dropped_artifacts': len(spec['dropped_artifacts']),
            })

    with io.open(os.path.join(out_dir, 'index.json'), 'w', encoding='utf-8') as fh:
        json.dump({'processes': index, 'unknown_types': all_unknowns,
                   'errors': errors}, fh, indent=2, ensure_ascii=False)

    print('processes extracted : %d' % len(index))
    print('json files scanned  : %d' % len(json_files))
    print('extraction errors   : %d' % len(errors))
    for e in errors[:10]:
        print('   ! %s' % e)
    dropped_total = sum(i['dropped_artifacts'] for i in index)
    print('artifacts dropped   : %d (annotations/groups/associations/data refs)'
          % dropped_total)

    if all_unknowns:
        print('\n*** UNKNOWN ELEMENT TYPES (%d occurrences) ***'
              % len(all_unknowns))
        agg = {}
        for u in all_unknowns:
            k = (u['type'], u['bpmn_element'], u.get('selected_type_id'))
            agg.setdefault(k, []).append(u)
        for (t, tag, sel), items in sorted(agg.items(), key=lambda kv: -len(kv[1])):
            labels = [i['label'] for i in items if i['label']][:5]
            print('  Type=%s element=%s SelectedTypeId=%s  x%d  labels=%s'
                  % (t, tag, sel, len(items), labels))
    else:
        print('\nunknown types       : none')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2]))
