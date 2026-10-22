#!/usr/bin/env python3
"""Route the maintained unfilled PLL to the existing slot13 access metal.

No pad, harness configuration, RTL, device or macro-interior changes.
Run with container python3; output is a new disposable candidate.
"""

import argparse
import json
from pathlib import Path
import re

from package_slot13 import ROOT, copy_library, sha


def pins(text):
    result = {}
    for line in text.splitlines():
        if line.startswith('flabel '):
            fields = line.split()
            start = 3 if fields[2] == 's' else 2
            box = [int(v) * .005 for v in fields[start:start + 4]]
            result[fields[-1]] = (fields[1], (box[0] + box[2]) / 2,
                                  (box[1] + box[3]) / 2)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or not output.is_relative_to(ROOT / 'layout/build'):
        parser.error('output must be a NEW directory under layout/build')
    library = ROOT / 'layout/core/mag'
    wrapper = ROOT.parent / 'sg13cmos5l_ocd_chipalooza/magic/slot13_wrapper.mag'
    text = wrapper.read_text()
    if 'string FIXED_BBOX 0 0 107430 54600\n' not in text:
        raise ValueError('review changed slot13 boundary')
    access, core = pins(text), pins((library / 'pll_core.mag').read_text())
    mapping = dict(VDD='vdd_1v2', VSS='vss_1v2', IREF='ibias0',
                   ref_clk='s13_an[0]', clk_out='s13_an[1]',
                   reset_n='reset', enable='enable')
    mapping.update({f'div_ratio[{i}]': f'dig_in[{i}]' for i in range(10)})
    mapping.update({f'test_div_select[{i}]': f'dig_in[{10+i}]' for i in range(2)})
    if set(mapping) != set(core) or not set(mapping.values()) <= set(access):
        raise ValueError('review changed core/wrapper interface')
    sections, routes = {}, []
    net = None

    def rect(layer, x1, y1, x2, y2):
        values = [round(v * 200) for v in (x1, y1, x2, y2)]
        if any(abs(n / 200 - v) > 1e-8 for n, v in zip(values, (x1, y1, x2, y2))):
            raise ValueError(f'off-grid route {layer}: {values}')
        sections.setdefault(layer, []).append('rect ' + ' '.join(map(str, values)))
        routes.append(dict(net=net, layer=layer, bounds_native=values))

    def wire(layer, points, width=.22):
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            if x1 != x2 and y1 != y2:
                raise ValueError('non-Manhattan route')
            rect(layer, min(x1, x2)-width/2, min(y1, y2)-width/2,
                 max(x1, x2)+width/2, max(y1, y2)+width/2)

    def via(level, x, y, narrow=False):
        if level == 4:
            for metal, width in ((4, .8), (5, 2.)):
                rect(f'metal{metal}', x-width/2, y-width/2, x+width/2, y+width/2)
            width = .62
        else:
            for metal in (level, level+1):
                w, h = (.3, .22) if narrow and metal == 3 else (.4, .4)
                rect(f'metal{metal}', x-w/2, y-h/2, x+w/2, y+h/2)
            # Native Magic contact includes the CIF surround; stream-out
            # generates the PDK's 0.19-um physical Via2/Via3 cut.
            width = .2
        rect(f'via{level}', x-width/2, y-width/2, x+width/2, y+width/2)

    # Clock routes stay outside the guarded analog blocks. A short M4
    # antenna jumper isolates the long M2/M3 reference route until M4 forms.
    # The reference uses the existing analog/digital channel, not cell interiors.
    for net, column, track, escape in [('ref_clk', 310., 251., 520.),
                                       ('clk_out', 505., None, 505.)]:
        _, cx, cy = core[net]
        _, px, py = access[mapping[net]]
        wire('metal3', [(cx, cy), (column, cy)])
        via(3, column, cy)
        if track is not None:
            jumper_y = cy + 1.5
            wire('metal4', [(column, cy), (column, jumper_y)])
            via(3, column, jumper_y)
            via(2, column, jumper_y)
            wire('metal2', [(column, jumper_y), (column, track)])
            via(2, column, track)
            wire('metal3', [(column, track), (escape, track)])
            via(2, escape, track)
            wire('metal2', [(escape, track), (escape, py)])
            via(2, escape, py)
        else:
            wire('metal4', [(column, cy), (column, py)])
            via(3, escape, py)
        wire('metal3', [(escape, py), (px, py)])

    # Configuration fanout: M2 verticals in the left margin, M3 tracks in
    # the empty upper channel, M4 descents above the digital access pins.
    controls = [*[f'div_ratio[{i}]' for i in range(10)],
                *[f'test_div_select[{i}]' for i in range(2)], 'reset_n', 'enable']
    for i, net in enumerate(controls):
        _, px, py = access[mapping[net]]
        layer, cx, cy = core[net]
        column = 3.5 + .8*i if i < 12 else (2.7 if i == 12 else 1.9)
        track = 230. + .8*i
        wire('metal3', [(px, py), (column, py)])
        via(2, column, py, narrow=True)
        wire('metal2', [(column, py), (column, track)])
        via(2, column, track)
        if layer == 'metal3':
            escape = 309. if net == 'reset_n' else 308.
            wire('metal3', [(cx, cy), (escape, cy)])
            via(3, escape, cy)
            cx = escape
        wire('metal3', [(column, track), (cx, track)])
        via(3, cx, track)
        wire('metal4', [(cx, track), (cx, cy)])

    net = 'IREF'
    _, cx, cy = core[net]
    _, px, py = access[mapping[net]]
    wire('metal3', [(cx, cy), (13.5, cy)], .4)
    via(2, 13.5, cy)
    wire('metal2', [(13.5, cy), (13.5, py)], .4)
    via(2, 13.5, py)
    wire('metal3', [(13.5, py), (px, py)], .4)

    net = 'VDD'
    wire('metal5', [(12., 206.), (9.5, 206.), (9.5, 50.), (1., 50.)], 2.)
    net = 'VSS'
    wire('metal4', [(4.7, 220.), (4.7, 80.)], 2.)
    for y in (220., 80.):
        for dy in (-1., 0., 1.):
            via(4, 4.7, y+dy)
    wire('metal5', [(12., 220.), (4.7, 220.)], 2.)
    rect('metal5', 3.7, 215., 17., 225.)
    wire('metal5', [(4.7, 80.), (1., 80.)], 2.)

    copy_library(library, output / 'mag')
    bounds = re.search(r'^string FIXED_BBOX (.*)$', (library/'pll_core.mag').read_text(), re.M)[1]
    insert = '\n'.join([*(line for layer, lines in sections.items()
                           for line in [f'<< {layer} >>', *lines]),
                        'use pll_core Xpll', 'transform 1 0 0 0 1 0', 'box '+bounds]) + '\n'
    text = text.replace('<< labels >>', insert+'<< labels >>', 1)
    (output/'mag/slot_13.mag').write_text(text)
    (output/'manifest.json').write_text(json.dumps(dict(
        stage='connected slot13 routing candidate; NOT signoff', mapping=mapping,
        wrapper_sha256=sha(wrapper), core_sha256=sha(library/'pll_core.mag'),
        routing_rectangles=routes, input_files_sha256={str(p.relative_to(ROOT)):sha(p)
            for p in library.iterdir() if p.suffix in ('.mag','.gds')},
        limitations=['Existing direct analog access terminals, no pad replacement',
                     'Reset low asserts PLL reset; ibias0 must supply 2 uA',
                     'Unused wrapper accesses intentionally not connected to PLL',
                     'Pad loading, antenna, density, full RC and electrical checks required']), indent=2)+'\n')
    print(output/'mag/slot_13.mag')


if __name__ == '__main__':
    main()
