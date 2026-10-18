"""Directed charge-pump baseline: functional groups and explicit analog routing.

Coordinates are CIC units (10000 per µm). Device total widths are preserved;
the provider records explicit refingering. Per-device guards are retained;
this is not a common-centroid array.
"""

import cicpy as cic


ROW_PITCH = 400000
ROWS = (
    ('XM_PBIAS_SINK', 'XM_IREF', 'XM_DOWN_SINK', 'XM_DOWN_SWITCH'),
    ('XM_PBIAS', 'XM_UP_SOURCE', 'XM_UP_SWITCH', 'XM_UP_INV_P', 'XM_UP_INV_N'),
)
NODES = {
    'XM_PBIAS_SINK': ['PBIAS', 'IREF', 'VSS', 'VSS'],
    'XM_IREF': ['IREF', 'IREF', 'VSS', 'VSS'],
    'XM_DOWN_SINK': ['N_DOWN', 'IREF', 'VSS', 'VSS'],
    'XM_DOWN_SWITCH': ['VCTRL', 'DOWN', 'N_DOWN', 'VSS'],
    'XM_PBIAS': ['PBIAS', 'PBIAS', 'VDD', 'VDD'],
    'XM_UP_SOURCE': ['P_UP', 'PBIAS', 'VDD', 'VDD'],
    'XM_UP_SWITCH': ['VCTRL', 'UP_B', 'P_UP', 'VDD'],
    'XM_UP_INV_P': ['UP_B', 'UP', 'VDD', 'VDD'],
    'XM_UP_INV_N': ['UP_B', 'UP', 'VSS', 'VSS'],
}


def place(top, provider):
    devices = {device.name: device for device in top.ckt.instances}
    if {name: device.nodes for name, device in devices.items()} != NODES:
        raise ValueError('charge-pump topology changed; update the directed recipe')
    for row, names in enumerate(ROWS):
        x = 0
        for name in names:
            if name == 'XM_UP_INV_P':
                x += 100000  # 10 µm extra separation from the quiet/current core.
            placed = top.addInstance(devices[name], x, row * ROW_PITCH)
            data = provider.metadata[name]
            if data['parameters']['m'] != '1':
                raise ValueError('this recipe requires m=1')
            data['translation'] = [int(placed.x1) - data['bounds'][0],
                                   int(placed.y1) - data['bounds'][1]]
            data['row'] = row
            data['group'] = ('switching-inverter' if '_INV_' in name else
                             'output-switch' if name.endswith('_SWITCH') else
                             'nmos-mirror' if row == 0 else 'pmos-mirror')
            x = int(placed.x2) + 20000
    top.updateBoundingRect()


def route(top, metadata):
    """M1 local access, M2 escapes, M3 channels, M4 common-point bridges.

    Only the named net's via connects an escape to a channel. Quiet and
    switching supplies have independent M3 branches to the common M4 feed.
    """
    def rect(layer, x, y, w, h):
        top.add(cic.Rect(layer, x, y, w, h))

    def wire(layer, a, b, width=4000):
        if a[0] != b[0] and a[1] != b[1]:
            raise ValueError('directed wires must be Manhattan segments')
        rect(layer, min(a[0], b[0]) - width // 2,
             min(a[1], b[1]) - width // 2,
             abs(a[0] - b[0]) + width, abs(a[1] - b[1]) + width)

    def via(level, x, y):
        # Magic's 200 nm tile exports a 190 nm physical via cut.
        width = 3200 if level == 1 else 4000
        rect(f'M{level}', x - width // 2, y - width // 2, width, width)
        rect(f'VIA{level}', x - 1000, y - 1000, 2000, 2000)
        rect(f'M{level + 1}', x - 2000, y - 2000, 4000, 4000)

    def array(level, x, y):
        for dx in (-2200, 2200):
            for dy in (-2200, 2200):
                via(level, x + dx, y + dy)
        for metal in (level, level + 1):
            rect(f'M{metal}', x - 4200, y - 4200, 8400, 8400)

    # Channel IDs distinguish supply branches without inventing circuit nets.
    upper = [('shield_low', 'VSS', 100000), ('IREF', 'IREF', 110000),
             ('PBIAS', 'PBIAS', 120000), ('VCTRL', 'VCTRL', 130000),
             ('shield_high', 'VSS', 140000),
             ('DOWN', 'DOWN', 210000)]
    lower = [('VSS_quiet', 'VSS', -40000), ('VDD_quiet', 'VDD', -70000),
             ('VSS_switch', 'VSS', -100000), ('VDD_switch', 'VDD', -130000)]
    bridges = {net: -30000 - index * 15000 for index, net in enumerate(
        ('IREF', 'PBIAS', 'VCTRL', 'P_UP', 'N_DOWN', 'UP_B', 'DOWN', 'UP', 'VDD', 'VSS'))}
    # Keep the two 2-µm supply spines clear of each other and signal spines.
    bridges['VDD'], bridges['VSS'] = -170000, -205000
    endpoints = []
    for name, data in metadata.items():
        ox, origin_y = data['translation']
        pins = data['pins']
        cy = (pins['D'][0][1] + pins['D'][0][3]) // 2
        oy = origin_y + cy
        stripes = pins['D'] + pins['S']
        xmin = min((r[0] + r[2]) // 2 for r in stripes)
        xmax = max((r[0] + r[2]) // 2 for r in stripes)
        single = int(data['parameters']['ng']) == 1
        accesses = {}
        for terminal in ('D', 'S'):
            points = []
            for shape in pins[terminal]:
                px, py = (shape[0] + shape[2]) // 2, (shape[1] + shape[3]) // 2
                if py != cy:
                    raise ValueError('unsupported MOS diffusion access height')
                vx = (-10000 if terminal == 'D' else 10000) if single else px
                wire('M1', (ox + px, oy), (ox + vx, oy), 1600)
                via(1, ox + vx, oy)
                points.append((ox + vx, oy))
            local_y = oy + (10000 if terminal == 'D' else -8000)
            escape_x = ox + (xmax + 8000 if terminal == 'D' else xmin - 8000)
            for px, py in points:
                wire('M2', (px, py), (px, local_y))
            wire('M2', (min(p[0] for p in points), local_y),
                 (max(p[0] for p in points), local_y))
            edge = max(p[0] for p in points) if terminal == 'D' else min(p[0] for p in points)
            wire('M2', (edge, local_y), (escape_x, local_y))
            accesses[terminal] = (escape_x, local_y)

        # The native M1 gate strap connects the fingers. Access outside the
        # D/S escape columns rather than dropping vias into their narrow pitch.
        shape = pins['G'][0]
        gx, gy = (shape[0] + shape[2]) // 2, (shape[1] + shape[3]) // 2 - cy
        gate_y = 9000 if single and gy < 6000 else gy
        gate_x = xmin - 17000
        wire('M1', (ox + gx, oy + gy), (ox + gx, oy + gate_y), 1600)
        wire('M1', (ox + gx, oy + gate_y), (ox + gate_x, oy + gate_y), 1600)
        via(1, ox + gate_x, oy + gate_y)
        accesses['G'] = (ox + gate_x, oy + gate_y)

        shape, = pins['B']
        by = origin_y + (shape[1] + shape[3]) // 2
        bx = ox + xmax + 13500
        # The entire native ring is contacted; stitch its bottom segment.
        wire('M1', (ox, by), (bx + 2200, by), 3200)
        for dx in (-2200, 2200):
            via(1, bx + dx, by)
        wire('M2', (bx - 2200, by), (bx + 2200, by))
        accesses['B'] = (bx, by)
        for terminal, net in zip(('D', 'G', 'S', 'B'), data['nodes']):
            side = 'upper' if terminal in ('D', 'G') else 'lower'
            channel = net
            if side == 'lower' and net in ('VDD', 'VSS'):
                channel += '_switch' if '_INV_' in name else '_quiet'
            endpoints.append((data['row'], side, channel, net, accesses[terminal]))

    # UP only drives the adjacent inverter pair. Keep it local instead of
    # exposing the tiny input gates to a full-width, multi-metal antenna.
    up = [p for r, s, c, n, p in endpoints if n == 'UP']
    if len(up) != 2:
        raise ValueError('expected two inverter UP gate accesses')
    up_y = max(p[1] for p in up) + 5000
    for x, y in up:
        wire('M2', (x, y), (x, up_y))
        via(2, x, up_y)
    wire('M3', (min(p[0] for p in up), up_y), (max(p[0] for p in up), up_y))
    top.addPortFromRect('UP', cic.Rect('M3', max(p[0] for p in up), up_y - 2000, 4000, 4000))

    # Switched-current nodes join adjacent source/switch devices locally,
    # rather than making a round trip through the global channel bank.
    for net in ('P_UP', 'N_DOWN'):
        points = [p for r, s, c, n, p in endpoints if n == net]
        if len(points) != 2:
            raise ValueError(f'expected two {net} accesses')
        x = sum(p[0] for p in points) // 2 // 50 * 50
        for px, py in points:
            via(2, px, py)
            wire('M3', (px, py), (x, py))
            via(3, x, py)
        wire('M4', (x, points[0][1]), (x, points[1][1]))

    # Keep the inverter's output bus above its native guard geometry, but
    # below the quiet channel bank. Its only load is the nearby UP switch.
    up_b = [p for r, s, c, n, p in endpoints if n == 'UP_B']
    if len(up_b) != 3:
        raise ValueError('expected three UP_B accesses')
    bus_y = max(data['translation'][1] + data['bounds'][3]
                for data in metadata.values() if data['row'] == 1) + 15000
    for x, y in up_b:
        wire('M2', (x, y), (x, bus_y))
        via(2, x, bus_y)
    wire('M3', (min(p[0] for p in up_b), bus_y),
         (max(p[0] for p in up_b), bus_y))

    # Output bridge beside the switches, not at the opposite macro edge.
    bridges['VCTRL'] = max(p[0] for r, s, c, n, p in endpoints if n == 'VCTRL') + 10000
    rails = {}
    for row in range(len(ROWS)):
        for side, channels in (('upper', upper), ('lower', lower)):
            for channel, net, offset in channels:
                points = [p for r, s, c, n, p in endpoints if (r, s, c) == (row, side, channel)]
                if not points and not channel.startswith('shield_'):
                    continue
                y = row * ROW_PITCH + offset
                width = 20000 if channel.startswith(('VDD_', 'VSS_')) else 4000
                bridge_x = bridges[net]
                right = int(top.x2) if channel.startswith('shield_') else max(p[0] for p in points)
                wire('M3', (bridge_x, y), (right, y), width)
                if net in ('VDD', 'VSS'):
                    array(3, bridge_x, y)
                else:
                    via(3, bridge_x, y)
                rails.setdefault(net, []).append(y)
                for x, py in points:
                    if width == 20000:
                        # Widen below the local D/S landings, not beside the
                        # single-finger device's opposite diffusion via.
                        wire('M2', (x, py), (x, py - 5000))
                        wire('M2', (x, py - 5000), (x, y), 8000)
                        array(2, x, y)
                    else:
                        wire('M2', (x, py), (x, y))
                        via(2, x, y)
    for net, ys in rails.items():
        x = bridges[net]
        width = 20000 if net in ('VDD', 'VSS') else 4000
        wire('M4', (x, min(ys)), (x, max(ys)), width)
        if net in top.ckt.nodes:
            top.addPortFromRect(net, cic.Rect('M4', x - width // 2, min(ys), width, width))
    top.updateBoundingRect()
