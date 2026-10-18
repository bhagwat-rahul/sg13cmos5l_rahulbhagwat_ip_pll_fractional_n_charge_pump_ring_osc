"""Native passive accesses and directed, quiet loop-filter routing.

CMOM uses M2–M4 internally: escape its labeled M4 terminals outward before
widening, and never route another net over its fingers on those layers.
Coordinates are 10000 CIC units per micrometre.
"""

from fractions import Fraction
import re

import cicpy as cic


PORTS = {'rhigh': ['R1', 'R2', 'B'], 'cap_cmomf': ['c1', 'c2']}


def read_device(path, model):
    text = path.read_text()
    a, b = re.search(r'^magscale (\d+) (\d+)$', text, re.M).groups()
    unit = Fraction(100 * int(a), int(b))
    rectangles, labels, layer = [], {}, None
    for line in text.splitlines():
        fields = line.split()
        if line.startswith('<< '):
            layer = fields[1]
        elif line.startswith('rect ') and layer not in ('checkpaint', 'error_p', 'error_s'):
            rectangles.append((layer, [int(unit * int(v)) for v in fields[1:5]]))
        elif line.startswith('rlabel ') and fields[-1] in PORTS[model]:
            labels[fields[-1]] = (int(unit * int(fields[2])), int(unit * int(fields[3])))
    if set(labels) != set(PORTS[model]):
        raise ValueError(f'{path}: missing passive terminals')
    bounds = [min(r[0] for _, r in rectangles), min(r[1] for _, r in rectangles),
              max(r[2] for _, r in rectangles), max(r[3] for _, r in rectangles)]
    layers = {pin: ('M4' if model == 'cap_cmomf' else 'M1' if pin == 'B' else 'M2')
              for pin in PORTS[model]}
    access = {'M1': ('metal1', 'psubdiffcont'), 'M2': ('metal2', 'via1'),
              'M4': ('metal4', 'via3')}
    for pin, (x, y) in labels.items():
        if not any(layer in access[layers[pin]] and r[0] <= x <= r[2] and r[1] <= y <= r[3]
                   for layer, r in rectangles):
            raise ValueError(f'{path}: no {layers[pin]} access at {pin}')
    # Tiny virtual access rectangles preserve exact native label anchors.
    # A wide landing centered on a CMOM edge could short adjacent fingers.
    pins = {p: [[x - 50, y - 50, x + 50, y + 50]] for p, (x, y) in labels.items()}
    return bounds, pins, layers


def place_and_route(top, provider):
    expected = {'XR1': ['VCTRL', 'FILTER_ZERO', 'VSS'],
                'XC1A': ['FILTER_ZERO', 'VSS'], 'XC2': ['VCTRL', 'VSS']}
    if {d.name: d.nodes for d in top.ckt.instances} != expected:
        raise ValueError('loop-filter topology changed; review recipe')
    positions = {'XC1A': (100000, 100000), 'XC2': (1300000, 100000),
                 'XR1': (1300000, 600000)}
    accesses = {}
    for device in top.ckt.instances:
        placed = top.addInstance(device, *positions[device.name])
        data = provider.metadata[device.name]
        ox, oy = int(placed.x1) - data['bounds'][0], int(placed.y1) - data['bounds'][1]
        data['translation'] = [ox, oy]
        for pin, shapes in data['pins'].items():
            x1, y1, x2, y2 = shapes[0]
            accesses[device.name, pin] = (ox + (x1 + x2) // 2, oy + (y1 + y2) // 2)

    def wire(layer, a, b, width=4000):
        if a[0] != b[0] and a[1] != b[1]:
            raise ValueError('non-Manhattan filter route')
        top.add(cic.Rect(layer, min(a[0], b[0]) - width // 2,
                         min(a[1], b[1]) - width // 2,
                         abs(a[0] - b[0]) + width, abs(a[1] - b[1]) + width))

    def via(level, point):
        x, y = point
        for metal in (level, level + 1):
            top.add(cic.Rect(f'M{metal}', x - 2000, y - 2000, 4000, 4000))
        top.add(cic.Rect(f'VIA{level}', x - 1000, y - 1000, 2000, 2000))

    # Complete the native resistor terminal's M1 enclosure without changing
    # its poly resistance geometry. Also join the native peripheral M1 tiles.
    for pin in ('R1', 'R2'):
        x, y = accesses['XR1', pin]
        top.add(cic.Rect('M1', x - 5000, y - 2000, 10000, 4000))

    # FILTER_ZERO: left of the large capacitor, then above its entire body.
    p = accesses['XC1A', 'c1']
    wire('M4', p, (50000, p[1]), 2000)
    wire('M4', (50000, p[1]), (50000, 1150000))
    p = accesses['XR1', 'R2']
    via(2, p)
    via(3, p)
    wire('M4', p, (p[0], 1150000))
    for x in (50000, p[0]):
        via(3, (x, 1150000))
    wire('M3', (50000, 1150000), (p[0], 1150000))

    # VCTRL occupies the gap between capacitors, never their finger area.
    p = accesses['XC2', 'c1']
    wire('M4', p, (1180000, p[1]), 2000)
    r = accesses['XR1', 'R1']
    via(2, r)
    wire('M3', r, (1180000, r[1]))
    via(3, (1180000, r[1]))
    wire('M4', (1180000, p[1]), (1180000, r[1]))
    top.addPortFromRect('VCTRL', cic.Rect('M3', 1178000, r[1] - 2000, 4000, 4000))

    # Dedicated quiet return: broad upper strap, outside both CMOM bodies.
    ground_xs = []
    for name in ('XC1A', 'XC2'):
        p = accesses[name, 'c2']
        escape_y = positions[name][1] + provider.metadata[name]['bounds'][3] + 20000
        wire('M4', p, (p[0], escape_y), 2000)
        wire('M4', (p[0], escape_y), (p[0], 1180000), 20000)
        via(3, (p[0], 1180000))
        ground_xs.append(p[0])
    p = accesses['XR1', 'B']
    via(1, p)
    via(2, p)
    # The resistor end is only ~0.7 um above its guard access. Widen the
    # return outside the resistor, not underneath the FILTER_ZERO landing.
    wire('M3', p, (1360000, p[1]))
    wire('M3', (1360000, p[1]), (1680000, p[1]), 20000)
    via(3, (1680000, p[1]))
    wire('M4', (1680000, p[1]), (1680000, 1180000), 20000)
    via(3, (1680000, 1180000))
    wire('M3', (min(ground_xs), 1180000), (1680000, 1180000), 20000)
    top.addPortFromRect('VSS', cic.Rect('M3', 1678000, 1178000, 4000, 4000))
    top.updateBoundingRect()
