#!/usr/bin/env python3
"""Experimental native-Magic fill, not electrical/signoff qualification.

Uses an immutable pll_analog checker snapshot and its exported GDS. CMOS5L
filler sizes/spacing follow the installed decks; no generic digital filler
cells or shared PDK edits. Optional --feol screens paired active/poly islands
and active-only edge fill. Run with the container's KLayout-enabled Python.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re

import klayout.db as db


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cell', choices=('pll_analog', 'pll_core'), default='pll_analog')
    parser.add_argument('--feol', action='store_true', help='also screen active/poly fill with unchanged keepouts')
    parser.add_argument('--bounds-um', type=float, nargs=4, metavar=('X1', 'Y1', 'X2', 'Y2'),
                        help='allocated fill boundary; must enclose the existing core boundary')
    parser.add_argument('--routing-manifest', type=Path,
                        help='compact CIC manifest: audited layer-specific power-routing masks and passive-device keepouts')
    args = parser.parse_args()
    report, output = args.report.resolve(), args.output.resolve()
    macro = Path(__file__).resolve().parents[1]
    build = (macro if args.cell == 'pll_analog' else macro.parents[1]) / 'layout/build'
    if not output.is_relative_to(build.resolve()):
        parser.error('output must be below layout/build')
    if output.exists():
        parser.error('output must be new; retain earlier candidates')
    hashes = json.loads((report / 'inputs.json').read_text())
    sources = {name: (report / 'mag' / name).read_bytes() for name in hashes}
    for name, data in sources.items():
        if hashlib.sha256(data).hexdigest() != hashes[name]:
            raise ValueError(f'snapshot changed: {name}')
    layout = db.Layout()
    stream = report / f'{args.cell}.gds'
    stream_hash = hashlib.sha256(stream.read_bytes()).hexdigest()
    if stream_hash != json.loads((report / 'cmom_annotations.json').read_text())['annotated_sha256']:
        raise ValueError('exported GDS changed after checker annotation audit')
    layout.read(str(stream))
    top = layout.cell(args.cell)
    instances = list(top.each_inst())
    analog_blocks = {'charge_pump', 'loop_filter', 'ring_oscillator'}
    expected = ([analog_blocks] if args.cell == 'pll_analog' else
                [{'pll_analog', 'pll_digital'}, analog_blocks | {'pll_digital'}])
    if not any({i.cell.name for i in instances} == names and len(instances) == len(names)
               for names in expected):
        raise ValueError('review fill keepouts for changed analog hierarchy')
    text = sources[f'{args.cell}.mag'].decode()
    fill_name = 'cic_analog_metal_fill' if args.cell == 'pll_analog' else 'cic_core_metal_fill'
    if re.search(rf'^use {fill_name} ', text, re.M):
        raise ValueError('input already contains this fill')
    scale = re.search(r'^magscale (\d+) (\d+)$', text, re.M)
    if scale.groups() != ('1', '2'):
        raise ValueError('review native fill coordinate conversion for changed magscale')
    bounds = [int(v) for v in re.search(r'^string FIXED_BBOX (.*)$', text, re.M)[1].split()]
    if args.bounds_um:
        expanded = [round(v / .005) for v in args.bounds_um]
        if any(abs(v * .005 - um) > 1e-9 for v, um in zip(expanded, args.bounds_um)):
            raise ValueError('fill boundary is off the native grid')
        if not (expanded[0] <= bounds[0] < bounds[2] <= expanded[2]
                and expanded[1] <= bounds[1] < bounds[3] <= expanded[3]):
            raise ValueError('fill boundary must enclose the existing core boundary')
        bounds = expanded
        text = re.sub(r'^string FIXED_BBOX .*$',
                      'string FIXED_BBOX ' + ' '.join(map(str, bounds)), text, flags=re.M)
    # Native magscale 1/2 uses 5-nm coordinates. Geometry arithmetic below
    # uses KLayout integer DBU and snaps filler to the same 5-nm grid.
    def unit(um):
        n = round(um / layout.dbu)
        if abs(n * layout.dbu - um) > 1e-9:
            raise ValueError('requested dimension is off the stream grid')
        return n

    def native_rect(box):
        edges = (box.left, box.bottom, box.right, box.top)
        coords = [round(v * layout.dbu / .005) for v in edges]
        if any(abs(c * .005 - v * layout.dbu) > 1e-9 for c, v in zip(coords, edges)):
            raise ValueError('filler off native grid')
        return 'rect ' + ' '.join(map(str, coords))

    domain = db.Region(db.Box(*[unit(v * .005) for v in bounds]))
    metals = (8, 10, 30, 50, 126)
    protected = db.Region()
    for instance in instances:
        if args.cell == 'pll_core' and instance.cell.name == 'pll_analog':
            children = list(instance.cell.each_inst())
            if {i.cell.name for i in children} != {'charge_pump', 'loop_filter', 'ring_oscillator'}:
                raise ValueError('review analog sub-block keepouts')
            for child in children:
                protected.insert(child.bbox().transformed(instance.trans).enlarged(unit(10)))
        elif args.routing_manifest and instance.cell.name == 'loop_filter':
            children = list(instance.cell.each_inst())
            if (len(children) != 3
                    or sum(i.cell.name.startswith('cic_cap_cmomf_') for i in children) != 2
                    or sum(i.cell.name.startswith('cic_rhigh_') for i in children) != 1):
                raise ValueError('review filter passive-device keepouts for changed hierarchy')
            for child in children:
                protected.insert(child.bbox().transformed(instance.trans).enlarged(unit(10)))
            for number in metals:
                routes = db.Region(instance.cell.shapes(layout.layer(number, 0)))
                protected += routes.transformed(instance.trans).sized(unit(2))
        else:
            protected.insert(instance.bbox().enlarged(unit(10)))
    physical = {number: db.Region(top.begin_shapes_rec(layout.layer(number, 0)))
                for number in metals}
    routing_manifest_hash = None
    if args.routing_manifest:
        routing_manifest_hash = hashlib.sha256(args.routing_manifest.read_bytes()).hexdigest()
        routing = json.loads(args.routing_manifest.read_text())
        declared = {number: db.Region() for number in metals}
        sensitive = db.Region()
        if {i.cell.name for i in instances} != analog_blocks | {'pll_digital'}:
            raise ValueError('routing-aware fill requires the compact four-block hierarchy')
        for row in routing['routing_rectangles']:
            number = dict(zip(('M1', 'M2', 'M3', 'M4', 'M5'), metals))[row['layer']]
            box = db.Box(*[unit(v) for v in row['bounds_um']])
            declared[number].insert(box)
            if row['net'] not in ('VDD', 'VSS'):
                sensitive.insert(box.enlarged(unit(3.05 if number == 126 else 2)))
        # Do not use a stale or incomplete route annotation to authorize
        # fill underneath an unrecognized signal. Compare actual stream paint.
        for number in metals:
            actual = db.Region(top.shapes(layout.layer(number, 0)))
            if not (actual ^ declared[number]).is_empty():
                raise ValueError(f'routing manifest does not match top metal {number}')
        protected += sensitive
    else:
        for number in metals:
            protected += physical[number].sized(unit(3.05 if number == 126 else 2))
    available_by_layer = {}
    for number in metals:
        mask = physical[number].sized(unit(3.05 if number == 126 else 2))
        available_by_layer[number] = domain - protected - mask
    available = domain - protected
    sections, counts = [], {}
    for index, number in enumerate(metals, 1):
        # Coarse-to-fine top-metal islands recover space around routing
        # without narrowing the reviewed analog/routing keepouts. Rectangular
        # remnants use both orientations; TM1 filler stays 5–10 um wide with
        # margin above the deck's 3-um minimum filler-to-filler spacing.
        patterns = ([(10, 10, 3.05), (10, 5, 3.05), (5, 10, 3.05), (5, 5, 3.05)]
                    if index == 5 else [(4, 4, .6)])
        if args.routing_manifest and index != 5:
            patterns += [(4, 2, .6), (2, 4, .6), (2, 2, .6)]
        boxes = []
        bbox = domain.bbox()
        remaining = available_by_layer[number].dup()
        for width, height, gap in patterns:
            w, h = unit(width), unit(height)
            sx, sy = unit(width + gap), unit(height + gap)
            phases = [(0, 0)]
            if args.routing_manifest and index == 5 and width == height == 5:
                ox, oy = unit((width + gap) / 2), unit((height + gap) / 2)
                phases += [(ox, 0), (0, oy), (ox, oy)]
            for ox, oy in phases:
                placed = db.Region()
                for y in range(bbox.bottom + oy, bbox.top - h + 1, sy):
                    for x in range(bbox.left + ox, bbox.right - w + 1, sx):
                        box = db.Box(x, y, x + w, y + h)
                        if not (db.Region(box) - remaining).is_empty():
                            continue
                        boxes.append(box)
                        placed.insert(box)
                remaining -= placed.sized(unit(gap))
        if args.routing_manifest and index == 5:
            # Grow existing rectangles into spare edge slivers, without
            # changing the 5–10 um size limits or 3.05 um fill spacing.
            occupied = db.Region()
            for box in boxes:
                occupied.insert(box)
            for position, original in enumerate(boxes):
                others = occupied - db.Region(original)
                legal = available_by_layer[number] - others.sized(unit(3.05))
                box = original
                for edge, direction in ((2, 1), (3, 1), (0, -1), (1, -1)):
                    while True:
                        edges = [box.left, box.bottom, box.right, box.top]
                        edges[edge] += direction * unit(.5)
                        grown = db.Box(*edges)
                        if (grown.width() > unit(10) or grown.height() > unit(10)
                                or not (db.Region(grown) - legal).is_empty()):
                            break
                        box = grown
                occupied = others + db.Region(box)
                boxes[position] = box
        counts[f'm{index}fill'] = len(boxes)
        sections.extend([f'<< m{index}fill >>', *map(native_rect, boxes)])
    if args.feol:
        active, poly = db.Region(), db.Region()
        bbox = domain.bbox()
        width, pitch = unit(4.95), unit(5.6)
        for row, y in enumerate(range(bbox.bottom, bbox.top - width + 1, pitch)):
            for column, x in enumerate(range(bbox.left, bbox.right - width + 1, pitch)):
                box = db.Box(x, y, x + width, y + width)
                if not (db.Region(box) - available).is_empty():
                    continue
                # Stagger paired tiles to keep poly islands separated. Every
                # tenth row is active-only to avoid excess poly coverage.
                if (row + column) % 2 == 0 and row % 10 != 0:
                    poly.insert(box)
                    active.insert(box.enlarged(-unit(.2)))
                else:
                    active.insert(box)
        # Recover boundary remnants without partly overlapping poly or
        # violating active-to-active space. The paired tiles above already
        # enclose their active islands by 0.2 um (> GFil.j's 0.18 um).
        remaining = available - active.sized(unit(.45)) - poly.sized(unit(.2))
        for size in (2.5, 1.2):
            width, pitch = unit(size), unit(size + .45)
            placed = db.Region()
            for y in range(bbox.bottom, bbox.top - width + 1, pitch):
                for x in range(bbox.left, bbox.right - width + 1, pitch):
                    box = db.Box(x, y, x + width, y + width)
                    if (db.Region(box) - remaining).is_empty():
                        placed.insert(box)
            active += placed
            remaining -= placed.sized(unit(.45))
        for layer, region in (('difffill', active), ('polyfill', poly)):
            sections.append(f'<< {layer} >>')
            for polygon in region.each():
                if polygon.area() != polygon.bbox().area():
                    raise ValueError('FEOL filler is not a rectangle')
                sections.append(native_rect(polygon.bbox()))
            counts[layer] = region.count()
    output.mkdir(parents=True)
    if args.routing_manifest:
        # Sidecar for the harness's GDS-tech fill pass, not submission paint.
        # Place it with exactly the same transform as pll_core. Its FILLBLOCK
        # and DIFFBLOCK purposes preserve these analog exclusions at chip level.
        keepouts = db.Layout()
        keepouts.dbu = layout.dbu
        keepout_cell = keepouts.create_cell(f'{args.cell}_fill_keepouts')
        for layer in ((160, 0), (1, 23)):
            keepout_cell.shapes(keepouts.layer(*layer)).insert(protected.merged())
        keepouts.write(str(output / 'fill_keepouts.gds'))
    for name, data in sources.items():
        if name.endswith('.mag'):
            saved = data.decode()
            for backing in set(re.findall(r'^string GDS_FILE (.+)$', saved, re.M)):
                filename = Path(backing).name
                if filename not in sources:
                    raise ValueError(f'unsnapshotted readonly GDS: {backing}')
                saved = saved.replace(f'string GDS_FILE {backing}\n',
                                      f'string GDS_FILE {output / filename}\n')
            data = saved.encode()
        (output / name).write_bytes(data)
    (output / f'{fill_name}.mag').write_text('\n'.join([
        'magic', 'tech ihp-sg13cmos5l', 'magscale 1 2', 'timestamp 0',
        *sections, '<< end >>', '']))
    use = (f'use {fill_name} fill_screen\n'
           'transform 1 0 0 0 1 0\nbox ' + ' '.join(map(str, bounds)) + '\n')
    (output / f'{args.cell}.mag').write_text(text.replace('<< labels >>', use + '<< labels >>', 1))
    (output / 'fill_manifest.json').write_text(json.dumps({
        'stage': 'experimental floating fill; NOT signoff',
        'input_report': str(report), 'source_mag_sha256': hashes,
        'source_gds_sha256': stream_hash,
        'recipe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'routing_manifest_sha256': routing_manifest_hash,
        'top_routing_geometry_xor': 'empty' if args.routing_manifest else 'not requested',
        'harness_keepout_sidecar': 'fill_keepouts.gds' if args.routing_manifest else None,
        'routing_mask_policy': ('layer-specific power; all-layer signal protection; 10-um passive-device keepouts'
                                if args.routing_manifest else 'conservative all-layer routing and macro-box keepouts'),
        'available_area_um2': {str(n): r.area() * layout.dbu ** 2
                               for n, r in available_by_layer.items()},
        'feol_available_area_um2': available.area() * layout.dbu ** 2,
        'fill_bounds_um': [v * .005 for v in bounds],
        'block_keepout_um': 10, 'physical_routing_keepout_um': 2,
        'topmetal1_routing_keepout_um': 3.05,
        'counts': counts, 'active_poly_fill': args.feol,
        'limitations': 'No substrate/EM/ESD or post-fill electrical qualification',
    }, indent=2) + '\n')
    print(output, counts)


if __name__ == '__main__':
    main()
