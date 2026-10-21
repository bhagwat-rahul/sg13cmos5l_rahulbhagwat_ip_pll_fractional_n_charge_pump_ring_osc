#!/usr/bin/env python3
"""Slot13 packing experiment: move protected macros, never resize devices.

Run with CIC Python in IIC-OSIC-TOOLS. Reuses maintained guarded analog
subblocks and readonly frozen digital geometry. No fill, pad adapter or RC
qualification. Outputs a new candidate without changing maintained sources.
"""

import argparse
import json
from pathlib import Path
import re
import shutil

import cicpy as cic

from integrate import ROOT, FROZEN, SOURCE, Leaves, sha, subcircuits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'layout/build') or output.exists():
        parser.error('output must be a NEW directory under layout/build/')
    library = ROOT / 'layout/core/mag'
    wrapper = ROOT.parent / 'sg13cmos5l_ocd_chipalooza/magic/slot13_wrapper.mag'
    slot_text = wrapper.read_text()
    scale = re.search(r'^magscale (\d+) (\d+)$', slot_text, re.M)
    unit = .01 * int(scale[1]) / int(scale[2])
    slot = [int(v) * unit for v in re.search(
        r'^string FIXED_BBOX (.*)$', slot_text, re.M)[1].split()]
    if slot != [0., 0., 537.15, 273.]:
        raise ValueError(f'review placement against changed slot boundary: {slot}')
    for row in (FROZEN / 'SHA256SUMS').read_text().splitlines():
        digest, name = row.split(maxsplit=1)
        if sha(FROZEN / name) != digest:
            raise ValueError(f'frozen package changed: {name}')
    # The assembled top is an output, not an input. Excluding it allows
    # promotion without invalidating the candidate's source provenance.
    inputs = {str(p.relative_to(ROOT)): sha(p) for p in library.iterdir()
              if p.suffix in ('.mag', '.gds') and p.name != 'pll_core.mag'}
    inputs.update({str(p.relative_to(ROOT)): sha(p) for p in
                   (SOURCE, Path(__file__), ROOT / 'scripts/pll/integrate.py',
                    ROOT / 'layout/core/routing.tech', FROZEN / 'SHA256SUMS',
                    FROZEN / 'lef/pll_digital.lef')})
    mag = output / 'mag'
    mag.mkdir(parents=True)
    shutil.copy2(library / 'pll_digital.gds', mag / 'pll_digital.gds')
    tech = ROOT / 'layout/core/routing.tech'
    rules = cic.Rules(str(tech))
    design = cic.MagicDesign('ihp-sg13cmos5l', rules)
    cells = ('charge_pump', 'loop_filter', 'ring_oscillator', 'pll_digital')
    provider = Leaves({name: library for name in cells}, mag)
    design.registerPrimitiveProvider(provider)
    ports = {n: p for n, p, _ in subcircuits(SOURCE)}['pll_core']
    connections = {
        'Xcp': ('charge_pump', ['VDD', 'up', 'down', 'IREF', 'VCTRL', 'VSS']),
        'Xfilter': ('loop_filter', ['VCTRL', 'VSS']),
        'Xvco': ('ring_oscillator', ['VDD', 'vco_clk', 'VCTRL', 'VSS']),
        'Xdigital': ('pll_digital', ['VDD', 'VSS', 'ref_clk', 'vco_clk', 'reset_n', 'enable',
            *[f'div_ratio[{i}]' for i in range(10)],
            *[f'test_div_select[{i}]' for i in range(2)],
            'feedback_unused', 'pll_unused', 'clk_out', 'up', 'down'])}
    source = output / 'placement.spice'
    source.write_text('\n'.join(
        '.subckt ' + c + ' ' + ' '.join(provider.canonical_port_order(c)) + '\n.ends ' + c
        for c in cells) + '\n.subckt pll_core ' + ' '.join(ports) + '\n' +
        '\n'.join(n + ' ' + ' '.join(nodes) + ' ' + c
                  for n, (c, nodes) in connections.items()) + '\n.ends pll_core\n')
    top = design.readFromSpice(str(source), 'pll_core')
    positions = {'Xcp': (15, 135), 'Xfilter': (15, 15),
                 'Xvco': (195, 25), 'Xdigital': (315, 35)}
    endpoints, bounds = {}, {}
    for instance in top.ckt.instances:
        x, y = positions[instance.name]
        placed = top.addInstance(instance, round(x * 10000), round(y * 10000))
        data = provider.metadata[instance.name]
        dx, dy = int(placed.x1) - data['bounds'][0], int(placed.y1) - data['bounds'][1]
        bounds[instance.name] = [(dx + data['bounds'][0]) / 10000,
                                 (dy + data['bounds'][1]) / 10000,
                                 (dx + data['bounds'][2]) / 10000,
                                 (dy + data['bounds'][3]) / 10000]
        for pin, net in zip(provider.canonical_port_order(instance.subcktName), instance.nodes):
            a, b, c, d = data['pins'][pin]['shape']
            endpoints[instance.name, net] = (data['pins'][pin]['layer'],
                                            (dx + (a + c) // 2) / 10000,
                                            (dy + (b + d) // 2) / 10000)

    routing = []
    current_net = 'VCTRL'

    def rect(layer, x1, y1, x2, y2):
        if layer.startswith('M'):
            routing.append(dict(net=current_net, layer=layer,
                                bounds_um=[round(v * 200) / 200 for v in (x1, y1, x2, y2)]))
        return cic.Rect(layer, round(x1 * 10000), round(y1 * 10000),
                        round((x2 - x1) * 10000), round((y2 - y1) * 10000))

    def wire(layer, points, width=.4):
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            if x1 != x2 and y1 != y2:
                raise ValueError('non-Manhattan route')
            top.add(rect(layer, min(x1, x2) - width / 2, min(y1, y2) - width / 2,
                         max(x1, x2) + width / 2, max(y1, y2) + width / 2))

    def via(level, x, y):
        width, cut = (2., .62) if level == 4 else (.4, .2)
        for n in (level, level + 1):
            landing = .8 if level == 4 and n == 4 else width
            top.add(rect(f'M{n}', x - landing / 2, y - landing / 2,
                         x + landing / 2, y + landing / 2))
        top.add(rect(f'VIA{level}', x - cut / 2, y - cut / 2, x + cut / 2, y + cut / 2))

    def access(instance, net, metal):
        layer, x, y = endpoints[instance, net]
        if instance == 'Xcp' and layer == 'M4' and net not in ('VDD', 'VSS'):
            y -= .2  # Existing child via is at the rail center, not label center.
        for n in range(min(int(layer[-1]), metal), max(int(layer[-1]), metal)):
            if instance == 'Xvco' and net in ('VDD', 'VSS') and n == 3:
                # Match its existing two-cut supply access; a center cut
                # would violate spacing to both native cuts.
                for offset in (-.22, .22):
                    via(n, x + offset, y)
            else:
                via(n, x, y)
        return x, y

    def port(net, layer, x, y, width=.4):
        top.addPortFromRect(net, rect(layer, x - width / 2, y - width / 2,
                                     x + width / 2, y + width / 2))

    # Short quiet trunk outside passive fingers and oscillator devices.
    ys = []
    for instance in ('Xcp', 'Xfilter', 'Xvco'):
        x, y = access(instance, 'VCTRL', 3)
        wire('M3', [(x, y), (185, y)])
        via(3, 185, y)
        ys.append(y)
    wire('M4', [(185, min(ys)), (185, max(ys))])

    current_net = 'vco_clk'
    ax, ay = access('Xvco', 'vco_clk', 3)
    dx, dy = access('Xdigital', 'vco_clk', 3)
    wire('M3', [(ax, ay), (305, ay)])
    via(3, 305, ay)
    wire('M4', [(305, ay), (305, dy)])
    via(3, 305, dy)
    wire('M3', [(305, dy), (dx, dy)])
    for net, rail, escape in [('up', 192, 480), ('down', 196, 485)]:
        current_net = net
        ax, ay = access('Xcp', net, 5)
        dx, dy = access('Xdigital', net, 3)
        wire('M3', [(dx, dy), (escape, dy)])
        via(3, escape, dy)
        via(4, escape, dy)
        wire('M5', [(ax, ay), (ax, rail), (escape, rail), (escape, dy)], 2.)

    lef = (FROZEN / 'lef/pll_digital.lef').read_text()
    for net, rail in [('VDD', 206), ('VSS', 220)]:
        current_net = net
        branches = []
        for instance in ('Xcp', 'Xvco'):
            x, y = access(instance, net, 4)
            if instance == 'Xcp' and net == 'VSS':
                # Escape below CP instead of cutting through its quiet circuitry.
                wire('M4', [(x, y), (x, 128)], 2.)
                via(3, x, 128)
                wire('M3', [(x, 128), (8, 128)], 2.)
                via(3, 8, 128)
                x, y = 8, 128
            branches.append((x, y, 2.))
        if net == 'VSS':
            x, y = access('Xfilter', net, 3)
            wire('M3', [(x, y), (180, y)], 2.)
            via(3, 180, y)
            branches.append((180, y, 2.))
        body = re.search(r'  PIN ' + net + r'\n(.*?)  END ' + net + r'\n', lef, re.S)[1]
        for shape in re.findall(r'RECT ([^;]+);', body):
            a, b, c, d = map(float, shape.split())
            branches.append((315 + (a + c) / 2, 35 + d, 1.))
        for x, y, width in branches:
            wire('M4', [(x, y), (x, rail + 1.5)], width)
            for offset in (-1., 0., 1.):
                via(4, x, rail + offset)
        wire('M5', [(12, rail), (max(x for x, _, _ in branches), rail)], 10.)
        port(net, 'M5', 12, rail, 10.)

    current_net = 'IREF'
    x, y = access('Xcp', 'IREF', 3)
    wire('M3', [(x, y), (10, y)])
    port('IREF', 'M3', 10, y)
    for net, track in [('ref_clk', 300), ('reset_n', 305), ('enable', 310)]:
        current_net = net
        x, y = access('Xdigital', net, 3)
        wire('M3', [(x, y), (track, y)])
        port(net, 'M3', track, y)
    for net in ports:
        if net.startswith(('div_ratio[', 'test_div_select[')):
            current_net = net
            x, y = access('Xdigital', net, 4)
            wire('M4', [(x, y), (x, 178)])
            port(net, 'M4', x, 178)
    current_net = 'clk_out'
    x, y = access('Xdigital', 'clk_out', 3)
    wire('M3', [(x, y), (490, y)])
    port('clk_out', 'M3', 490, y)
    top.updateBoundingRect()
    envelope = [int(getattr(top, axis)) / 10000 for axis in ('x1', 'y1', 'x2', 'y2')]
    area = (envelope[2] - envelope[0]) * (envelope[3] - envelope[1])
    fraction = area / ((slot[2] - slot[0]) * (slot[3] - slot[1]))
    if not (slot[0] <= envelope[0] < envelope[2] <= slot[2]
            and slot[1] <= envelope[1] < envelope[3] <= slot[3]) or fraction > .70:
        raise ValueError(f'core envelope exceeds slot or 70% target: {envelope}, {fraction}')
    cic.MagicPrinter(str(mag), rules).print(design)
    for name, digest in inputs.items():
        if sha(ROOT / name) != digest:
            raise ValueError(f'input changed while generating: {name}')
    (output / 'manifest.json').write_text(json.dumps(dict(
        stage='slot13 compact routing experiment; NOT signoff', inputs_sha256=inputs,
        slot_wrapper_sha256=sha(wrapper), slot_bounds_um=slot,
        group_bounds_um=bounds, positions_um=positions,
        routing_rectangles=routing,
        core_bounds_um=envelope, core_envelope_area_um2=area,
        slot_envelope_fraction=fraction,
        limitations='No resized devices or core fill; actual wrapper/pad routing, PDN current capacity, coupling and electrical qualification pending.'), indent=2) + '\n')
    print(f'Generated {mag / "pll_core.mag"}')


if __name__ == '__main__':
    main()
