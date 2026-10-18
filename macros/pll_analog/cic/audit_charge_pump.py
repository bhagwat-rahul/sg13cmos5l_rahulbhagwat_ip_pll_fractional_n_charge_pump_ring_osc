#!/usr/bin/env python3
"""Audit this candidate's saved guards, mirror geometry and extracted bulk ties.

Geometric tie-distance bounds and DC resistance connectivity are not substrate
attenuation, random mismatch, EM or ESD qualification. Run full DRC/LVS too.
"""

import argparse
import heapq
import json
import math
from pathlib import Path
import re


def geometry(path):
    scale, layer, rectangles = .01, None, []
    for line in path.read_text().splitlines():
        fields = line.split()
        if line.startswith('magscale '):
            scale = .01 * int(fields[1]) / int(fields[2])
        elif line.startswith('<< '):
            layer = fields[1]
        elif line.startswith('rect '):
            rectangles.append((layer, [int(v) * scale for v in fields[1:5]]))
    return rectangles


def distance(point, rectangle):
    x, y = point
    x1, y1, x2, y2 = rectangle
    return math.hypot(max(x1 - x, 0, x - x2), max(y1 - y, 0, y - y2))


def connected(rectangles):
    seen = {0}
    pending = [0]
    while pending:
        a = rectangles[pending.pop()]
        for index, b in enumerate(rectangles):
            if index not in seen and max(a[0], b[0]) <= min(a[2], b[2]) + 1e-9 and max(a[1], b[1]) <= min(a[3], b[3]) + 1e-9:
                seen.add(index)
                pending.append(index)
    return len(seen) == len(rectangles)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('pex', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.candidate / 'manifest.json').read_text())
    saved = (args.candidate / 'charge_pump.mag').read_text()
    transforms = {name: [int(v) for v in values.split()] for name, values in re.findall(
        r'^use \S+ (\S+)[^\n]*\ntransform ([^\n]+)', saved, re.M)}
    for name in manifest['devices']:
        a, b, x, d, e, y = transforms[name]
        if (a, b, d, e) != (1, 0, 0, 1):
            raise ValueError('this matching audit requires same-orientation saved placements')
    graph, mos = {}, []
    for line in args.pex.read_text().splitlines():
        fields = line.split()
        if fields and fields[0].startswith('R'):
            _, a, b, value = fields
            graph.setdefault(a, []).append((b, float(value)))
            graph.setdefault(b, []).append((a, float(value)))
        elif fields and fields[0].startswith('X'):
            mos.append(fields)

    def paths(start):
        costs, queue = {start: 0.}, [(0., start)]
        while queue:
            cost, node = heapq.heappop(queue)
            if cost != costs[node]:
                continue
            for other, resistance in graph.get(node, []):
                if cost + resistance < costs.get(other, math.inf):
                    costs[other] = cost + resistance
                    heapq.heappush(queue, (cost + resistance, other))
        return costs

    supplies = {rail: paths(rail) for rail in ('VDD', 'VSS')}
    bulk_paths = []
    for device in mos:
        model, bulk = device[5], device[4]
        rail = 'VDD' if model == 'sg13_lv_pmos' else 'VSS'
        if bulk not in supplies[rail]:
            raise ValueError(f'{device[0]} bulk has no resistive path to {rail}')
        if bulk in supplies['VSS' if rail == 'VDD' else 'VDD']:
            raise ValueError('VDD/VSS short in extracted resistance graph')
        bulk_paths.append(dict(device=device[0], bulk=bulk, rail=rail,
                               shortest_path_ohm=supplies[rail][bulk]))
    guards = []
    for name, data in manifest['devices'].items():
        is_pmos = 'pmos' in data['cell']
        prefix = 'nsub' if is_pmos else 'psub'
        shapes = geometry(args.candidate / (data['cell'] + '.mag'))
        contacts = [r for layer, r in shapes if layer == prefix + 'diffcont']
        ring = [r for layer, r in shapes if layer in (prefix + 'diff', prefix + 'diffcont')]
        active = [r for layer, r in shapes if layer in (
            ('pmos', 'pdiff', 'pdiffc') if is_pmos else ('nmos', 'ndiff', 'ndiffc'))]
        if not contacts or not active or not connected(ring):
            raise ValueError(f'{name}: missing contacts/active or disconnected guard diffusion')
        bounds = [min(r[0] for r in active), min(r[1] for r in active),
                  max(r[2] for r in active), max(r[3] for r in active)]
        x1, y1, x2, y2 = bounds
        sides = [any(r[0] <= x1 and r[2] >= x2 and r[1] > y2 for r in contacts),
                 any(r[0] <= x1 and r[2] >= x2 and r[3] < y1 for r in contacts),
                 any(r[1] <= y1 and r[3] >= y2 and r[2] < x1 for r in contacts),
                 any(r[1] <= y1 and r[3] >= y2 and r[0] > x2 for r in contacts)]
        if not all(sides):
            raise ValueError(f'{name}: contacts do not surround active on all four sides')
        corners = [(x, y) for x in (bounds[0], bounds[2]) for y in (bounds[1], bounds[3])]
        # For any chosen contact, convex distance reaches its maximum on a
        # bounding-box corner. Choosing the best contact yields an upper bound
        # for every active point, not merely sampled nearest-corner distances.
        bound = min(max(distance(point, contact) for point in corners) for contact in contacts)
        if bound > 20:
            raise ValueError(f'{name}: cannot bound active-to-tie distance below 20um')
        guards.append(dict(instance=name, contacted_guard=prefix, continuous_diffusion=True,
                           contacts=len(contacts), contacted_on_all_four_sides=True,
                           active_to_tie_upper_bound_um=bound,
                           body_net=data['nodes'][3], translation_um=[v / 10000 for v in data['translation']]))
    devices = manifest['devices']
    mirror = ['XM_PBIAS_SINK', 'XM_IREF', 'XM_DOWN_SINK']
    if len({devices[name]['cell'] for name in mirror}) != 1:
        raise ValueError('NMOS mirrors no longer share identical primitive geometry')
    for name in mirror:
        if devices[name]['parameters']['w'] != '4.0u' or devices[name]['parameters']['l'] != '0.50u':
            raise ValueError('unexpected mirror size')
    report = {'guards': guards, 'bulk_paths': bulk_paths,
              'max_bulk_shortest_path_ohm': max(r['shortest_path_ohm'] for r in bulk_paths),
              'matching': {'nmos_identical_primitives': mirror,
                           'orientation': 'same; verified saved transforms are identity + translation',
                           'common_centroid': False,
                           'pmos_total_width_ratio': '8:7; physical source is seven 1um fingers',
                           'limitations': 'Outer devices have different global environments; no gradient cancellation or statistical mismatch claim'},
              'limitations': 'Shortest path is not effective resistance or a current/EM limit; metal connectivity is established with LVS. No substrate-noise/ESD qualification.'}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Audited {len(guards)} guarded devices, {len(bulk_paths)} extracted MOS bulks; {args.output}')


if __name__ == '__main__':
    main()
