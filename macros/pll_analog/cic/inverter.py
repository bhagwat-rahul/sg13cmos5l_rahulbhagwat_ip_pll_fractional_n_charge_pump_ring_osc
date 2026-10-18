"""Directed, individually guarded current-starved inverter experiment.

PMOS and NMOS branches have the same left-to-right current-source/switch
ordering. Local current nodes stay in their rows; explicit local joins and
side bridges cross supplies on separate layers. Coordinates are 10000 CIC
units per micrometre.
"""

import cicpy as cic


NODES = {
    'inverter': {'XM1': ['net1', 'VBP', 'VDD', 'VDD'],
                 'XM2': ['VOUT', 'VIN', 'net1', 'VDD'],
                 'XM3': ['VOUT', 'VIN', 'net2', 'VSS'],
                 'XM4': ['net2', 'VBN', 'VSS', 'VSS']},
    'vco_buffer': {'XM1': ['net1', 'VIN', 'VDD', 'VDD'],
                   'XM2': ['net1', 'VIN', 'VSS', 'VSS'],
                   'XM3': ['VOUT', 'net1', 'VDD', 'VDD'],
                   'XM4': ['VOUT', 'net1', 'VSS', 'VSS']},
}
ROWS = {'inverter': (('XM4', 'XM3'), ('XM1', 'XM2')),
        'vco_buffer': (('XM2', 'XM4'), ('XM1', 'XM3'))}
PITCH = {'inverter': 180000, 'vco_buffer': 110000}


def place(top, provider, cell, row_pitch=None):
    pitch = PITCH[cell] if row_pitch is None else row_pitch
    devices = {d.name: d for d in top.ckt.instances}
    if {n: d.nodes for n, d in devices.items()} != NODES[cell]:
        raise ValueError(f'{cell} topology changed; review recipe')
    for row, names in enumerate(ROWS[cell]):
        x = 0
        for name in names:
            placed = top.addInstance(devices[name], x, row * pitch)
            data = provider.metadata[name]
            if data['parameters']['m'] != '1':
                raise ValueError('inverter recipe requires m=1')
            data['translation'] = [int(placed.x1) - data['bounds'][0],
                                   int(placed.y1) - data['bounds'][1]]
            data['row'] = row
            x = int(placed.x2) + 20000
    top.updateBoundingRect()


def route(top, metadata, cell, row_pitch=None):
    pitch = PITCH[cell] if row_pitch is None else row_pitch
    def rect(layer, x, y, w, h):
        top.add(cic.Rect(layer, x, y, w, h))

    def wire(layer, a, b, width=4000):
        if a[0] != b[0] and a[1] != b[1]:
            raise ValueError('non-Manhattan directed wire')
        rect(layer, min(a[0], b[0]) - width // 2, min(a[1], b[1]) - width // 2,
             abs(a[0] - b[0]) + width, abs(a[1] - b[1]) + width)

    def via(level, x, y):
        # Narrow local M2 escapes accommodate short-channel finger pitch.
        for metal in (level, level + 1):
            width = 3200 if metal in (1, 2) else 4000
            rect(f'M{metal}', x - width // 2, y - width // 2, width, width)
        rect(f'VIA{level}', x - 1000, y - 1000, 2000, 2000)

    endpoints = []
    for name, data in metadata.items():
        ox, oy = data['translation']
        pins = data['pins']
        stripes = pins['D'] + pins['S']
        xmin = min((r[0] + r[2]) // 2 for r in stripes)
        xmax = max((r[0] + r[2]) // 2 for r in stripes)
        cy = (pins['D'][0][1] + pins['D'][0][3]) // 2
        single = data['parameters']['ng'] == '1'
        access = {}
        for terminal, offset in (('D', 10000), ('S', -12000)):
            points = []
            for shape in pins[terminal]:
                x, y = (shape[0] + shape[2]) // 2, (shape[1] + shape[3]) // 2
                if y != cy:
                    raise ValueError('unexpected finger access height')
                vx = (-10000 if terminal == 'D' else 10000) if single else x
                # Both multifinger vias are below the gate strap, including
                # the buffer's 150-nm-wide fingers. Stagger by 600 nm to
                # respect M2 spacing at the 510-nm native contact pitch.
                vy = y if single else y + (-2000 if terminal == 'D' else -8000)
                wire('M1', (ox + x, oy + y), (ox + vx, oy + y), 1600)
                wire('M1', (ox + vx, oy + y), (ox + vx, oy + vy), 1600)
                via(1, ox + vx, oy + vy)
                points.append((ox + vx, oy + vy))
            y = oy + cy + offset
            for x, py in points:
                wire('M2', (x, py), (x, y), 3200)
            left, right = min(p[0] for p in points), max(p[0] for p in points)
            wire('M2', (left, y), (right, y), 3200)
            if single:
                x = points[0][0]
            else:
                x = ox + (xmax + 8000 if terminal == 'D' else xmin - 8000)
            wire('M2', (right if terminal == 'D' else left, y), (x, y), 3200)
            access[terminal] = (x, y)
        shape = pins['G'][0]
        gx, gy = (shape[0] + shape[2]) // 2, (shape[1] + shape[3]) // 2
        gate_y = cy + 9000 if single and gy - cy < 6000 else gy
        gate_x = xmin - 17000
        wire('M1', (ox + gx, oy + gy), (ox + gx, oy + gate_y), 1600)
        wire('M1', (ox + gx, oy + gate_y), (ox + gate_x, oy + gate_y), 1600)
        via(1, ox + gate_x, oy + gate_y)
        access['G'] = (ox + gate_x, oy + gate_y)
        shape, = pins['B']
        by = oy + (shape[1] + shape[3]) // 2
        bx = ox + xmax + 17000
        wire('M1', (ox, by), (bx + 2200, by), 3200)
        for dx in (-2200, 2200):
            via(1, bx + dx, by)
        wire('M2', (bx - 2200, by), (bx + 2200, by))
        access['B'] = (bx, by)
        endpoints.extend((data['row'], net, access[terminal])
                         for terminal, net in zip(('D', 'G', 'S', 'B'), data['nodes']))

    # Each bank is above its device row except the broad supply branch below.
    offsets = {'net1': 90000, 'net2': 90000, 'VBN': 100000, 'VBP': 100000,
               'VSS': -30000, 'VDD': -30000}
    if cell == 'inverter' and row_pitch is not None and pitch < 150000:
        # A compact PMOS row cannot overlap the original NMOS banks at
        # 9/10 um. Keep them below the NMOS gate accesses instead, separated
        # from VSS. Native device/guard geometry and all finger joins remain.
        offsets.update(net2=-10000, VBN=10000)
    # Both cells join the output drains directly on M4, rather than
    # detouring through the upper banks and a side column. Cross supply
    # branches without a via; native device geometry and guards stay intact.
    points = sorted([p for r, n, p in endpoints if n == 'VOUT'], key=lambda p: p[1])
    (x, y), (px, py) = points
    # The inverter's input M4 hop is nearby. Separate the output column
    # rather than increasing the opposite-phase VIN/VOUT sidewall coupling.
    output_x = px + (20000 if cell == 'inverter' else 0)
    for vx, vy in points:
        via(2, vx, vy)
        via(3, vx, vy)
        wire('M4', (vx, vy), (output_x, vy))
    wire('M4', (output_x, y), (output_x, py))
    top.addPortFromRect('VOUT', cic.Rect('M4', output_x - 2000, (y + py) // 100 * 50, 4000, 4000))
    endpoints = [(r, n, p) for r, n, p in endpoints if n != 'VOUT']
    if cell == 'inverter':
        # Join the switch gates locally instead of detouring through both
        # upper channel banks. Unlike the buffer, this column crosses the
        # broad VDD M2 branch: hop over that branch on M4, without a via at
        # the crossing. Keep all native devices and their guards untouched.
        points = sorted([p for r, n, p in endpoints if n == 'VIN'], key=lambda p: p[1])
        (x, y), (px, py) = points
        supply_y = pitch + offsets['VDD']
        if x != px or not y < supply_y - 20000 < supply_y + 20000 < py:
            raise ValueError('inverter gate geometry changed; review local VIN bridge')
        wire('M2', (x, y), (x, supply_y - 20000), 3200)
        wire('M2', (x, supply_y + 20000), (x, py), 3200)
        for landing_y in (supply_y - 20000, supply_y + 20000):
            via(2, x, landing_y)
            via(3, x, landing_y)
        wire('M4', (x, supply_y - 20000), (x, supply_y + 20000))
        top.addPortFromRect('VIN', cic.Rect('M4', x - 2000, supply_y, 4000, 4000))
        endpoints = [(r, n, p) for r, n, p in endpoints if n != 'VIN']
    elif cell == 'vco_buffer':
        # Join the small first-stage gates locally on M2. Taking this net
        # through the upper channel bank/M4 bridge exceeds GDS antenna limits.
        points = sorted([p for r, n, p in endpoints if n == 'VIN'], key=lambda p: p[1])
        (x, y), (px, py) = points
        wire('M2', (x, y), (x, py), 3200)
        wire('M2', (x, py), (px, py), 3200)
        # Leave room for a parent's M2/M3/M4 landing above the VDD rail.
        port_y = max((y + py) // 100 * 50, pitch + offsets['VDD'] + 14000)
        top.addPortFromRect('VIN', cic.Rect('M2', x - 1600, port_y, 3200, 4000))
        endpoints = [(r, n, p) for r, n, p in endpoints if n != 'VIN']
        # Keep the interstage connection local as well: M4 joins each
        # first-stage drain to its adjacent second-stage gate, then joins
        # the rows on the left, away from the loaded VOUT column.
        points = [p for r, n, p in endpoints if n == 'net1']
        trunk_x = min(p[0] for p in points)
        for x, y in points:
            # No long M2 escape remains to satisfy minimum island area.
            rect('M2', x - 1600, y - 2400, 3200, 4800)
            via(2, x, y)
            via(3, x, y)
            wire('M4', (x, y), (trunk_x, y))
        wire('M4', (trunk_x, min(p[1] for p in points)),
             (trunk_x, max(p[1] for p in points)))
        endpoints = [(r, n, p) for r, n, p in endpoints if n != 'net1']
    for row in range(2):
        nets = list(dict.fromkeys(n for r, n, p in endpoints if r == row))
        for net in nets:
            points = [p for r, n, p in endpoints if r == row and n == net]
            y = row * pitch + offsets[net]
            supply = net in ('VDD', 'VSS')
            left = -10000 if net in ('VDD', 'VSS', 'VBP', 'VBN') else min(p[0] for p in points)
            right = max(p[0] for p in points)
            wire('M3', (left, y), (right, y), 20000 if supply else 4000)
            if supply:
                # Continuous same-net M2 under the redundant supply vias:
                # isolated source/body landings otherwise leave sub-rule gaps.
                wire('M2', (min(p[0] for p in points) - 4200, y),
                     (max(p[0] for p in points) + 4200, y), 8000)
            for x, py in points:
                wire('M2', (x, py), (x, y), 3200)
                if supply:
                    for dx in (-2200, 2200):
                        via(2, x + dx, y)
                    wire('M2', (x - 2200, y), (x + 2200, y))
                else:
                    via(2, x, y)
            if net in top.ckt.nodes:
                top.addPortFromRect(net, cic.Rect('M3', left, y - 2000, 4000, 4000))
    top.updateBoundingRect()
