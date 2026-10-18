"""Directed ring assembly from saved, guarded Magic leaf libraries.

No generic autorouting, device resizing, flattening or fill. Units: 0.1 nm.
"""

from fractions import Fraction
import hashlib
from pathlib import Path
import re

import cicpy as cic


class Leaves:
    def __init__(self, libraries, output):
        self.metadata = {}
        self.cells = {}
        self.hashes = {}
        for name, library in libraries.items():
            library = Path(library).resolve()
            for source in library.glob('*.mag'):
                target = output / source.name
                if target.exists() and target.read_bytes() != source.read_bytes():
                    # Independently generated identical PCells carry different
                    # save timestamps. No geometry, labels or properties may differ.
                    old = re.sub(r'^timestamp \d+\n', '', target.read_text(), flags=re.M)
                    new = re.sub(r'^timestamp \d+\n', '', source.read_text(), flags=re.M)
                    if old != new:
                        raise ValueError(f'conflicting leaf geometry: {source.name}')
                else:
                    target.write_bytes(source.read_bytes())
                self.hashes[str(source)] = hashlib.sha256(source.read_bytes()).hexdigest()
            text = (output / f'{name}.mag').read_text()
            scale = re.search(r'^magscale (\d+) (\d+)$', text, re.M)
            unit = Fraction(100 * int(scale[1]), int(scale[2]))
            bounds = [int(Fraction(v) * unit) for v in
                      re.search(r'^string FIXED_BBOX (.*)$', text, re.M)[1].split()]
            pins = {}
            for label, layer, coords, pin in re.findall(
                    r'^(flabel|rlabel) (metal[234]) s ([^\n]+)\nport (\d+) [^\n]+', text, re.M):
                fields = coords.split()
                shape = [int(Fraction(v) * unit) for v in fields[:4]]
                pins[fields[-1]] = {'layer': 'M' + layer[-1], 'shape': shape, 'order': int(pin)}
            if not pins:
                raise ValueError(f'no exported ports in {name}')
            self.cells[name] = {'bounds': bounds, 'pins': pins}

    def supports(self, design, name):
        return name in self.cells

    def canonical_port_order(self, name):
        return sorted(self.cells[name]['pins'], key=lambda p: self.cells[name]['pins'][p]['order']) if name in self.cells else []

    def generate(self, design, name, instance):
        data = self.cells[name]
        ox, oy, xmax, ymax = data['bounds']
        cell = cic.Cell()
        cell.name, cell.parent, cell.libshift = name, design, (ox, oy)
        cell.add(cic.Rect('PR', 0, 0, xmax - ox, ymax - oy))
        for pin, entry in data['pins'].items():
            x1, y1, x2, y2 = entry['shape']
            cell.add(cic.Port(pin, routeLayer=entry['layer'],
                              rect=cic.Rect(entry['layer'], x1 - ox, y1 - oy, x2 - x1, y2 - y1)))
        cell.updateBoundingRect()
        self.metadata[instance.name] = dict(data, cell=name, nodes=instance.nodes)
        return cell


def place_and_route(top, provider, shield_feedback=False, local_interstage=False):
    expected = {'x1': ['VDD', 'VBP', 'VCO_CORE', 'net1', 'VCTRL', 'VSS'],
                'x2': ['VDD', 'VBP', 'net1', 'net2', 'VCTRL', 'VSS'],
                'x3': ['VDD', 'VBP', 'net2', 'VCO_CORE', 'VCTRL', 'VSS'],
                'x_bias': ['VDD', 'VBP', 'VCTRL', 'VSS'],
                'x_buffer': ['VDD', 'VCO_CORE', 'VCO_OUT', 'VSS']}
    if {d.name: d.nodes for d in top.ckt.instances} != expected:
        raise ValueError('ring topology changed; review directed recipe')
    positions = {'x1': (0, 0), 'x2': (350000, 0), 'x3': (700000, 0),
                 'x_bias': (0, -300000), 'x_buffer': (700000, -440000)}
    endpoints = {}
    for device in top.ckt.instances:
        placed = top.addInstance(device, *positions[device.name])
        data = provider.metadata[device.name]
        ox, oy = int(placed.x1) - data['bounds'][0], int(placed.y1) - data['bounds'][1]
        data['translation'] = [ox, oy]
        order = provider.canonical_port_order(device.subcktName)
        if len(order) != len(device.nodes):
            raise ValueError('macro port count differs from schematic')
        for pin, net in zip(order, device.nodes):
            entry = data['pins'][pin]
            x1, y1, x2, y2 = entry['shape']
            endpoints.setdefault(net, []).append((device.name, entry['layer'],
                                                  ox + (x1 + x2) // 2, oy + (y1 + y2) // 2))

    def wire(layer, a, b, width=4000):
        if a[0] != b[0] and a[1] != b[1]:
            raise ValueError('non-Manhattan ring wire')
        top.add(cic.Rect(layer, min(a[0], b[0]) - width // 2,
                         min(a[1], b[1]) - width // 2,
                         abs(a[0] - b[0]) + width, abs(a[1] - b[1]) + width))

    def via(level, x, y, supply=False):
        # Supply stacks use two cuts with a continuous enclosing landing.
        for dx in (-2200, 2200) if supply else (0,):
            for metal in (level, level + 1):
                top.add(cic.Rect(f'M{metal}', x + dx - 2000, y - 2000, 4000, 4000))
            top.add(cic.Rect(f'VIA{level}', x + dx - 1000, y - 1000, 2000, 2000))
        if supply:
            for metal in (level, level + 1):
                wire(f'M{metal}', (x - 2200, y), (x + 2200, y))

    # Keep control below the stages: a top-side detour exceeds the tiny
    # bias gate's cumulative antenna budget even after an immediate M4 jump.
    # Retain upper feedback routing: the shorter below-array candidates
    # increased control-node ripple in the finite-impedance screening probe.
    channels = {'net1': 370000, 'net2': 385000, 'VCO_CORE': 400000,
                'VBP': 440000, 'VCTRL': -50000, 'VDD': 500000, 'VSS': 540000}
    access_tracks = {'VDD': -30000, 'VSS': -60000, 'VBP': -90000, 'VCTRL': -120000}
    if local_interstage:
        # Avoid the upper-bank detour for adjacent stage connections.
        # These M3 tracks lie between the leaf's VDD and PMOS-current banks;
        # M4 drops cross other M3 nets without a via. Keep the corridor at
        # the same offset from the PMOS banks when compacting the leaf;
        # otherwise longer parent drops cancel the shorter leaf wiring.
        bias_y = max(p[3] for p in endpoints['VBP'] if p[0] in ('x1', 'x2', 'x3'))
        channels.update(net1=bias_y - 80000, net2=bias_y - 65000,
                        VCO_CORE=bias_y + 80000)
    if shield_feedback:
        channels['VCO_CORE'] = -10000
    for net, points in endpoints.items():
        if net == 'VCO_OUT':
            _, layer, x, y = points[0]
            top.addPortFromRect(net, cic.Rect(layer, x - 2000, y - 2000, 4000, 4000))
            continue
        rail_y = channels[net]
        xs = []
        supply = net in ('VDD', 'VSS')
        for instance, layer, x, y in points:
            if instance == 'x_bias' and net == 'VCTRL':
                # The tiny bias gate cannot carry a long M3 escape before
                # M4 joins it to the much larger current-starver gate area.
                via(2, x, y)
                via(3, x, y)
            elif net in access_tracks:
                if layer == 'M2':
                    if supply:
                        # Bias VDD/VSS are at the same height; separate
                        # them below the leaf before crossing left on M3.
                        escape_y = y - (40000 if net == 'VDD' else 70000)
                        wire('M2', (x, y), (x, escape_y), 8000)
                        y = escape_y
                    via(2, x, y, supply)
                track = positions[instance][0] + access_tracks[net]
                wire('M3', (x, y), (track, y), 20000 if supply else 4000)
                via(3, track, y, supply)
                x = track
            elif layer == 'M2':
                via(2, x, y)
                via(3, x, y)
            elif layer != 'M4':
                raise ValueError(f'unreviewed clock access {instance}:{net}:{layer}')
            wire('M4', (x, y), (x, rail_y), 20000 if supply else 4000)
            via(3, x, rail_y, supply)
            xs.append(x)
        if net == 'VCO_CORE' and shield_feedback:
            # Cross each inverter control spine on M2, with grounded M3
            # between clock and M4 control. Shield returns join the existing
            # local VSS access; no device/guard or supply rail is displaced.
            cursor = min(xs)
            # A continuous grounded strip also separates the parallel M3
            # feedback/control trunks, not only their M4 crossing points.
            shield_y = -30000
            wire('M3', (min(xs), shield_y), (max(xs), shield_y), 20000)
            for instance in ('x2', 'x3'):
                control_x = positions[instance][0] + access_tracks['VCTRL']
                left, right = control_x - 30000, control_x + 30000
                wire('M3', (cursor, rail_y), (left, rail_y))
                via(2, left, rail_y)
                wire('M2', (left, rail_y), (right, rail_y))
                via(2, right, rail_y)
                ground_x = control_x + 20000
                wire('M3', (control_x - 10000, rail_y), (ground_x, rail_y))
                _, _, vss_x, vss_y = next(p for p in endpoints['VSS'] if p[0] == instance)
                via(3, ground_x, rail_y)
                via(3, ground_x, shield_y)
                wire('M4', (ground_x, shield_y), (ground_x, vss_y))
                via(3, ground_x, vss_y)
                wire('M3', (ground_x, vss_y), (vss_x, vss_y))
                cursor = right
            wire('M3', (cursor, rail_y), (max(xs), rail_y))
        else:
            wire('M3', (min(xs), rail_y), (max(xs), rail_y), 20000 if supply else 4000)
        if net in ('VDD', 'VSS', 'VCTRL'):
            top.addPortFromRect(net, cic.Rect('M3', min(xs) - 2000, rail_y - 2000, 4000, 4000))
    top.updateBoundingRect()
