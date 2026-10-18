"""Experimental directed analog assembly; units are 0.1 nm.

Keep the quiet CP/filter to the left of the switching ring. Separate return
branches meet only at the external supply entry. This is not an EM, substrate
coupling, ESD or signoff qualification.
"""

import cicpy as cic


def place_and_route(top, provider):
    expected = {'x_charge_pump': ['VDD', 'UP', 'DOWN', 'IREF', 'VCTRL', 'VSS'],
                'x_loop_filter': ['VCTRL', 'VSS'],
                'x_vco': ['VDD', 'VCO_CLK', 'VCTRL', 'VSS']}
    if {d.name: d.nodes for d in top.ckt.instances} != expected:
        raise ValueError('analog topology changed; review directed recipe')
    positions = {'x_charge_pump': (0, 0), 'x_loop_filter': (0, -1400000),
                 'x_vco': (2300000, 0)}
    pins = {}
    for device in top.ckt.instances:
        placed = top.addInstance(device, *positions[device.name])
        data = provider.metadata[device.name]
        ox, oy = int(placed.x1) - data['bounds'][0], int(placed.y1) - data['bounds'][1]
        data['translation'] = [ox, oy]
        for pin, net in zip(provider.canonical_port_order(device.subcktName), device.nodes):
            entry = data['pins'][pin]
            x1, y1, x2, y2 = entry['shape']
            pins[device.name, net] = (entry['layer'], ox + (x1 + x2) // 2,
                                     oy + (y1 + y2) // 2)

    def wire(layer, a, b, width=4000):
        if a[0] != b[0] and a[1] != b[1]:
            raise ValueError('non-Manhattan analog wire')
        top.add(cic.Rect(layer, min(a[0], b[0]) - width // 2,
                         min(a[1], b[1]) - width // 2,
                         abs(a[0] - b[0]) + width, abs(a[1] - b[1]) + width))

    def via(x, y, supply=False):
        for dx in (-2200, 2200) if supply else (0,):
            for layer in ('M3', 'M4'):
                top.add(cic.Rect(layer, x + dx - 2000, y - 2000, 4000, 4000))
            top.add(cic.Rect('VIA3', x + dx - 1000, y - 1000, 2000, 2000))
        if supply:
            for layer in ('M3', 'M4'):
                wire(layer, (x - 2200, y), (x + 2200, y))

    def port(net, layer, x, y, width=4000):
        top.addPortFromRect(net, cic.Rect(layer, x - width // 2, y - width // 2,
                                         width, width))

    # Quiet control trunk in the empty gap, not across oscillator devices.
    control_x = 2000000
    control_ys = []
    for instance in positions:
        layer, x, y = pins[instance, 'VCTRL']
        if instance == 'x_charge_pump':
            # CP labels start at the rail centre, not at its lower edge.
            # Reuse the existing child M3/M4 via at that rail centre.
            y -= 2000
        elif layer == 'M4':
            via(x, y)
        wire('M3', (x, y), (control_x, y))
        via(control_x, y)
        control_ys.append(y)
    wire('M4', (control_x, min(control_ys)), (control_x, max(control_ys)))

    # Each supply branch has its own strap up to the external entry region.
    for net, entry_x, entry_y, branches in (
            ('VDD', -400000, 1330000, [('x_charge_pump', 1130000), ('x_vco', 1370000)]),
            ('VSS', -300000, 1250000, [('x_charge_pump', -150000),
                                      ('x_loop_filter', 1210000), ('x_vco', 1290000)])):
        for instance, rail_y in branches:
            layer, x, y = pins[instance, net]
            if instance == 'x_loop_filter':
                wire('M3', (x, y), (1800000, y), 20000)
                x = 1800000
                via(x, y, True)
            elif layer == 'M3':
                via(x, y, True)
            wire('M4', (x, y), (x, rail_y), 20000)
            via(x, rail_y, True)
            wire('M3', (x, rail_y), (entry_x, rail_y), 20000)
            via(entry_x, rail_y, True)
            wire('M4', (entry_x, rail_y), (entry_x, entry_y), 40000)
        port(net, 'M4', entry_x, entry_y, 40000)

    # Change layers at the exposed pins rather than shorting the internal
    # M4 supply spines (DOWN) or output-buffer interstage bridge (VCO_CLK).
    for instance, net, exit_x in (('x_charge_pump', 'DOWN', -150000),
                                  ('x_charge_pump', 'IREF', -100000),
                                  ('x_charge_pump', 'UP', 820000),
                                  ('x_vco', 'VCO_CLK', 3550000)):
        layer, x, y = pins[instance, net]
        if net == 'UP':
            # Preserve the leaf's small M3 gate antenna; escape on M4.
            via(x, y)
            wire('M4', (x, y), (exit_x, y))
            port(net, 'M4', exit_x, y)
            continue
        if instance == 'x_charge_pump' and layer == 'M4':
            y -= 2000  # Existing child M3/M4 rail via; do not overlap its cut.
        elif layer == 'M4':
            via(x, y)
        wire('M3', (x, y), (exit_x, y))
        port(net, 'M3', exit_x, y)
    top.updateBoundingRect()
