#!/usr/bin/env python3
"""Experimental CIC placement with untouched native Magic SG13CMOS5L devices.

Run with the CIC virtualenv Python inside IIC-OSIC-TOOLS. Never writes the
manual layout library. This local MOS/passive adapter is not a complete PDK port.
"""

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path

import analog
import charge_pump
import cicpy as cic
import inverter
import loop_filter
import ring

HERE = Path(__file__).resolve().parent
PDK = Path(os.environ.get('PDK_ROOT', '/foss/pdks')) / 'ihp-sg13cmos5l'
RC = PDK / 'libs.tech/magic/ihp-sg13cmos5l.magicrc'


def read_device(path):
    """Preserve raw geometry; expose *all* labeled M1 terminal accesses.

    Magic units are 10 nm times magscale; CIC units here are 0.1 nm.
    Contact tiles include M1 even where there is no separate metal1 tile.
    """
    scale = Fraction(100)
    layer = None
    rectangles, labels = [], []
    for line in path.read_text().splitlines():
        fields = line.split()
        if line.startswith('magscale '):
            scale = Fraction(100 * int(fields[1]), int(fields[2]))
        elif line.startswith('<< '):
            layer = fields[1]
        elif line.startswith('rect ') and layer not in ('checkpaint', 'error_p', 'error_s'):
            coords = [Fraction(int(v)) * scale for v in fields[1:5]]
            if any(v.denominator != 1 for v in coords):
                raise ValueError('device geometry is not representable in CIC units')
            rectangles.append((layer, [int(v) for v in coords]))
        elif line.startswith('rlabel '):
            labels.append((fields[-1], [int(Fraction(int(v)) * scale)
                                        for v in fields[2:6]]))
    bounds = [min(r[1][0] for r in rectangles), min(r[1][1] for r in rectangles),
              max(r[1][2] for r in rectangles), max(r[1][3] for r in rectangles)]
    pins = {p: [] for p in ('D', 'G', 'S', 'B')}
    access_layers = {'metal1', 'ndiffc', 'pdiffc', 'polycont',
                     'psubdiffcont', 'nsubdiffcont'}
    for name, label in labels:
        terminal = re.fullmatch(r'([DGSB])\d*', name)
        if not terminal:
            continue
        x, y = (label[0] + label[2]) // 2, (label[1] + label[3]) // 2
        shapes = [r for layer, r in rectangles if layer in access_layers
                  and r[0] <= x <= r[2] and r[1] <= y <= r[3]]
        if not shapes:
            raise ValueError(f'{path.name}: no M1 access for {name}')
        shape = min(shapes, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))
        if shape not in pins[terminal[1]]:
            pins[terminal[1]].append(shape)
    if not all(pins.values()):
        raise ValueError(f'{path.name}: missing terminal: {pins}')
    # Native multifinger generation omits a label on the final edge diffusion.
    # Recover it from the verified alternating contact/gate chain, anchored by
    # the generator's D label, rather than assuming labels cover all fingers.
    contacts = sorted([r for layer, r in rectangles if layer in ('ndiffc', 'pdiffc')])
    gates = sorted([r for layer, r in rectangles if layer in ('nmos', 'pmos')])
    if len(contacts) != len(gates) + 1:
        raise ValueError(f'{path.name}: unsupported contact/gate topology')
    for index, gate in enumerate(gates):
        if not (contacts[index][2] < gate[0] < gate[2] < contacts[index + 1][0]):
            raise ValueError(f'{path.name}: non-alternating MOS contact chain')
    if contacts[0] not in pins['D']:
        raise ValueError(f'{path.name}: contact-chain polarity is not anchored by D')
    for terminal in ('D', 'S'):
        chain = contacts[0::2] if terminal == 'D' else contacts[1::2]
        if any(shape not in chain for shape in pins[terminal]):
            raise ValueError(f'{path.name}: labeled {terminal} disagrees with contact chain')
        pins[terminal] = chain
    return bounds, pins


class NativeDevices:
    """CIC provider delegating process geometry to the installed PDK generator."""

    def __init__(self, output, bottom_gate_contact):
        self.output = output
        self.metadata = {}
        self.options = dict(guard=1, full_metal=1, conn_gates=1, topc=1,
                            botc=int(bottom_gate_contact), doports=1, viasrc=0,
                            viadrn=0, viagate=0, set_x_to_guard=2.0, set_y_to_guard=2.0)

    def supports(self, design, name):
        return name in ('sg13_lv_nmos', 'sg13_lv_pmos', *loop_filter.PORTS)

    def canonical_port_order(self, name):
        if name in loop_filter.PORTS:
            return loop_filter.PORTS[name]
        return ['D', 'G', 'S', 'B'] if self.supports(None, name) else []

    def generate(self, design, name, instance):
        if not self.supports(design, name):
            raise ValueError(f'unsupported primitive {name}')
        props = instance.properties
        passive = name in loop_filter.PORTS
        keys = (('w', 'l', 'm', 'b') if name == 'rhigh' else
                ('w', 'l', 'm', 'mmin', 'mmax', 'subblock') if name == 'cap_cmomf' else
                ('w', 'l', 'ng', 'm'))
        params = {p: props[p] for p in keys}
        schematic_params = dict(params)
        if instance.name == 'XM_UP_SOURCE' and params == {
                'w': '7.0u', 'l': '0.50u', 'ng': '8', 'm': '1'}:
            # Eight symmetric 0.875-µm fingers round to 7.04 µm on the
            # native generator grid. Seven 1-µm fingers preserve total W.
            params['ng'] = '7'
        if any(not re.fullmatch(r'[0-9.eE+\-unmp]+', str(v)) for v in params.values()):
            raise ValueError(f'unsupported device parameters: {params}')
        if name == 'cap_cmomf':
            if params['mmin'] != '2' or params['mmax'] != '4':
                raise ValueError('review passive access routing for another CMOM metal stack')
            params.update(mmin='metal2', mmax='metal4')
        options = (dict(guard=1, bar=0, full_metal=1, vias=1, doports=1) if name == 'rhigh' else
                   dict(square=1) if name == 'cap_cmomf' else self.options)
        key = hashlib.sha256(json.dumps([name, params, options], sort_keys=True).encode()).hexdigest()[:12]
        cellname = f'cic_{name}_{key}'
        target = self.output / f'{cellname}.mag'
        with tempfile.TemporaryDirectory(dir=self.output) as directory:
            work = Path(directory)
            script = f'''crashbackups stop
drc off
load staging
box values 0 0 0 0
magic::gencell sg13cmos5l::{name} DUT -spice {' '.join(f'{k} {v}' for k, v in (params | options).items())}
writeall force
save staging
quit -noprompt
'''
            (work / 'generate.tcl').write_text(script)
            result = subprocess.run(['magic', '-dnull', '-noconsole', '-rcfile', str(RC),
                                     str(work / 'generate.tcl')], cwd=work,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            (self.output / f'{cellname}.log').write_text(result.stdout)
            (self.output / f'{cellname}.tcl').write_text(script)
            result.check_returncode()
            child = re.search(r'^use (\S+)', (work / 'staging.mag').read_text(), re.M)[1]
            target.write_bytes((work / f'{child}.mag').read_bytes())
        if name == "cap_cmomf":
            # The native PCell tags an ideal devcap, not the foundry model.
            # Preserve its physical geometry/ports, but use its saved physical
            # dimensions and stack for a hierarchical model-view X call.
            text = target.read_text()
            words = shlex.split(re.search(r"^string parameters (.*)$", text, re.M)[1])
            native = dict(zip(words[::2], words[1::2]))
            record = (
                "string device csubckt cap_cmomf 0 0 1 1 "
                f"w={native['w']}u l={native['l']}u "
                f"mmin={native['mmin'].removeprefix('metal')} "
                f"mmax={native['mmax'].removeprefix('metal')} "
                f"subblock={native['subblock']} c1 0 0 c2 0 0"
            )
            text, count = re.subn(r"^string device .*$", record, text, flags=re.M)
            if count != 1:
                raise ValueError(
                    f"{target}: expected one native capacitor device property"
                )
            target.write_text(text)
        if passive:
            bounds, pins, layers = loop_filter.read_device(target, name)
        else:
            bounds, pins = read_device(target)
            layers = dict.fromkeys(pins, 'M1')
        ox, oy, xmax, ymax = bounds
        cell = cic.Cell()
        cell.name, cell.parent = cellname, design
        cell.libshift = (ox, oy)
        cell.add(cic.Rect('PR', 0, 0, xmax - ox, ymax - oy))
        for name, shapes in pins.items():
            x1, y1, x2, y2 = shapes[0]
            cell.add(cic.Port(name, routeLayer=layers[name],
                              rect=cic.Rect(layers[name], x1 - ox, y1 - oy, x2 - x1, y2 - y1)))
        cell.updateBoundingRect()
        self.metadata[instance.name] = {'cell': cellname, 'parameters': params,
                                        'schematic_parameters': schematic_params,
                                        'generator_options': options,
                                        'bounds': bounds, 'pins': pins,
                                        'nodes': instance.nodes}
        return cell


def route_bias(top, metadata):
    """Directed two-device pilot; no generic signal/supply autorouter."""
    expected = {'XM1': ['VBP', 'VBP', 'VDD', 'VDD'],
                'XM2': ['VBP', 'VCTRL', 'VSS', 'VSS']}
    if {name: data['nodes'] for name, data in metadata.items()} != expected:
        raise ValueError('bias topology changed; update the directed recipe before routing')

    def rectangle(layer, x, y, width, height):
        top.add(cic.Rect(layer, x, y, width, height))

    def wire(layer, a, b, width):
        if a[0] != b[0] and a[1] != b[1]:
            raise ValueError('pilot wires must be Manhattan segments')
        rectangle(layer, min(a[0], b[0]) - width // 2,
                  min(a[1], b[1]) - width // 2,
                  abs(a[0] - b[0]) + width, abs(a[1] - b[1]) + width)

    def via(x, y):
        rectangle('M1', x - 1600, y - 1600, 3200, 3200)
        # Magic's via tile includes 5 nm M2 enclosure around the 190 nm cut.
        rectangle('VIA1', x - 1000, y - 1000, 2000, 2000)
        rectangle('M2', x - 2000, y - 2000, 4000, 4000)

    top_y = int(top.y2)
    vbp_y, control_y, supply_y = top_y + 15000, top_y + 6000, -10000
    vbp_points = []
    for name, data in metadata.items():
        ox, oy = data['translation']
        access = {}
        for terminal in ('D', 'S', 'G'):
            shape, = data['pins'][terminal]  # pilot deliberately supports ng=1 only
            x, y = (shape[0] + shape[2]) // 2, (shape[1] + shape[3]) // 2
            tx, ty = {'D': (-10000, 0), 'S': (10000, 0), 'G': (0, 6000)}[terminal]
            wire('M1', (ox + x, oy + y), (ox + tx, oy + ty), 1600)
            via(ox + tx, oy + ty)
            access[terminal] = (ox + tx, oy + ty)
        shape, = data['pins']['B']
        bx, by = ox + (shape[0] + shape[2]) // 2, oy + (shape[1] + shape[3]) // 2
        for dx in (-2200, 2200):
            via(bx + dx, by)
        wire('M1', (bx - 2200, by), (bx + 2200, by), 3200)
        wire('M2', (bx - 2200, by), (bx + 2200, by), 4000)
        wire('M2', (bx, by), (bx, supply_y), 4000)
        sx, sy = access['S']
        wire('M2', (sx, sy), (sx, supply_y), 4000)
        wire('M2', (bx, supply_y), (sx, supply_y), 4000)
        rail = cic.Rect('M2', bx - 4000, supply_y - 10000, 20000, 8000)
        rectangle('M2', bx - 4000, supply_y - 10000, 20000, 12000)
        top.addPortFromRect('VDD' if name == 'XM1' else 'VSS', rail)
        vbp_points.append(access['D'])
        if name == 'XM1':
            vbp_points.append(access['G'])
        else:
            gx, gy = access['G']
            wire('M2', (gx, gy), (gx, control_y), 4000)
            wire('M2', (gx, control_y), (int(top.x2) + 10000, control_y), 4000)
            top.addPortFromRect('VCTRL', cic.Rect('M2', gx, control_y - 2000, 4000, 4000))
    for x, y in vbp_points:
        wire('M2', (x, y), (x, vbp_y), 4000)
    left, right = min(p[0] for p in vbp_points), max(p[0] for p in vbp_points)
    wire('M2', (left, vbp_y), (right, vbp_y), 4000)
    top.addPortFromRect('VBP', cic.Rect('M2', left, vbp_y - 2000, 4000, 4000))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cell', choices=('vco_bias', 'charge_pump', 'inverter', 'vco_buffer', 'ring_oscillator', 'loop_filter', 'pll_analog'),
                        default='vco_bias')
    parser.add_argument('--leaf-library', action='append', default=[], metavar='CELL=DIR',
                        help='saved Magic libraries: ring leaves, or charge_pump/loop_filter/ring_oscillator for analog top')
    parser.add_argument('--shield-feedback', action='store_true',
                        help='ring-only experimental lower feedback route with grounded crossover shields')
    parser.add_argument('--local-interstage', action='store_true',
                        help='ring-only experimental short adjacent-stage clock routes')
    parser.add_argument('--inverter-row-pitch-um', type=float,
                        help='inverter-only row-pitch experiment; default remains 18 um')
    parser.add_argument('--schematic-library', type=Path, default=HERE.parent / 'schematic/xschem',
                        help='Xschem source directory; use the same library for LVS and electrical checks')
    parser.add_argument('--set-size', action='append', default=[], metavar='CELL.INSTANCE.PARAM=VALUE',
                        help='experiment on a copied schematic library; only oscillator MOS w/ng may change')
    parser.add_argument('--output', type=Path, required=True,
                        help='new, empty experiment directory (not the manual library)')
    args = parser.parse_args()
    if args.shield_feedback and args.cell != 'ring_oscillator':
        parser.error('--shield-feedback is only used for ring_oscillator')
    if args.local_interstage and args.cell != 'ring_oscillator':
        parser.error('--local-interstage is only used for ring_oscillator')
    row_pitch = None
    if args.inverter_row_pitch_um is not None:
        if args.cell != 'inverter':
            parser.error('--inverter-row-pitch-um is only used for inverter')
        pitch = Fraction(str(args.inverter_row_pitch_um)) * 10000
        if pitch <= 0 or pitch % 50:
            parser.error('row pitch must be positive and on the 5-nm grid')
        row_pitch = int(pitch)
    libraries = dict(entry.split('=', 1) for entry in args.leaf_library)
    if args.cell == 'ring_oscillator':
        if set(libraries) != {'inverter', 'vco_bias', 'vco_buffer'}:
            parser.error('ring requires exactly inverter, vco_bias and vco_buffer leaf libraries')
    elif args.cell == 'pll_analog':
        if set(libraries) != {'charge_pump', 'loop_filter', 'ring_oscillator'}:
            parser.error('analog top requires charge_pump, loop_filter and ring_oscillator libraries')
    elif libraries:
        parser.error('--leaf-library is only used for ring_oscillator or pll_analog')
    output = args.output.resolve()
    if not output.is_relative_to((HERE.parent / 'layout/build').resolve()):
        parser.error('experiment outputs must be below macros/pll_analog/layout/build/')
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        parser.error('output must be empty; keep previous candidates for comparison')
    schematic = args.schematic_library.resolve()
    if args.set_size:
        (output / 'schematic').mkdir()
        for source in schematic.iterdir():
            if source.is_file() and (source.suffix in ('.sch', '.sym') or source.name == 'xschemrc'):
                shutil.copy2(source, output / 'schematic' / source.name)
        schematic = output / 'schematic'
        for entry in args.set_size:
            match = re.fullmatch(r'(inverter|vco_bias|vco_buffer)\.(M[1-4])\.(w|ng)=((?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)u|[1-9][0-9]*)', entry)
            if not match:
                parser.error(f'invalid oscillator sizing override: {entry}')
            cell, device, parameter, value = match.groups()
            if (parameter == 'w' and not value.endswith('u')) or (parameter == 'ng' and not value.isdigit()):
                parser.error(f'width requires um; ng requires an integer: {entry}')
            if parameter == 'w' and float(value[:-1]) <= 0:
                parser.error(f'width must be positive: {entry}')
            path = schematic / f'{cell}.sch'
            text = path.read_text()
            pattern = r'(\{name=' + device + r'\n)(.*?)(^\})'
            def resize(m):
                body, count = re.subn(r'^' + parameter + r'=\S+$', parameter + '=' + value,
                                      m[2], flags=re.M)
                if count != 1:
                    raise ValueError(f'expected one {parameter} on {cell}.{device}')
                return m[1] + body + m[3]
            text, count = re.subn(pattern, resize, text, flags=re.M | re.S)
            if count != 1:
                raise ValueError(f'expected one device {cell}.{device}')
            path.write_text(text)
        (output / 'sizing.json').write_text(json.dumps(args.set_size, indent=2) + '\n')
    os.environ.update(PDK_ROOT=str(PDK.parent), PDK=PDK.name, PDKPATH=str(PDK),
                      STD_CELL_LIBRARY='sg13cmos5l_stdcell')
    # Layer aliases only: not a replacement for the foundry verification decks.
    technology = {'version': 2, 'technology': {'gamma': 50, 'grid': 5,
                                             'techlib': 'ihp-sg13cmos5l'},
                  'rules': {'CELL': {'space': 1000}},
                  'layers': {'PR': {'alias': '', 'number': 0, 'material': 'pnr'},
                             'M1': {'alias': 'metal1', 'number': 8, 'material': 'metal'},
                             'M2': {'alias': 'metal2', 'number': 10, 'material': 'metal'},
                             'M3': {'alias': 'metal3', 'number': 30, 'material': 'metal'},
                             'M4': {'alias': 'metal4', 'number': 50, 'material': 'metal'},
                             'VIA2': {'alias': 'via2', 'number': 29, 'material': 'cut',
                                      'previous': 'M2', 'next': 'M3'},
                             'VIA3': {'alias': 'via3', 'number': 49, 'material': 'cut',
                                      'previous': 'M3', 'next': 'M4'},
                             'VIA1': {'alias': 'via1', 'number': 19, 'material': 'cut',
                                      'previous': 'M1', 'next': 'M2'}}}
    rules_path = output / 'routing.tech'
    rules_path.write_text(json.dumps(technology, indent=2) + '\n')
    rules = cic.Rules(str(rules_path))
    design = cic.MagicDesign('ihp-sg13cmos5l', rules)
    provider = (ring.Leaves(libraries, output) if libraries else
                NativeDevices(output, bottom_gate_contact=args.cell == 'vco_bias'))
    design.registerPrimitiveProvider(provider)
    source = output / f'{args.cell}.spice'
    command = ('set spiceprefix 1; set lvs_netlist 0; set top_is_subckt 1; '
               'set lvs_ignore 1; set ev_precision 5; '
               f'set netlist_dir {{{output}}}; '
               f'xschem set netlist_name {{{source.name}}}; xschem netlist')
    with (output / 'xschem.log').open('w') as log:
        subprocess.run(['xschem', '-s', '-r', '-x', '-q', '--rcfile',
                        str(schematic / 'xschemrc'), '--command', command,
                        str(schematic / f'{args.cell}.sch')], cwd=schematic,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    circuit = source
    if args.cell in ('loop_filter', 'pll_analog'):
        # CIC treats simulator model directives as instances. Preserve the
        # raw Xschem export, and remove only these known model loads from
        # its circuit-only input, just as the independent LVS checker does.
        circuit = output / f'{args.cell}.circuit.spice'
        circuit.write_text(re.sub(
            r'(?im)^\.(?:lib[ \t]+cornerRES\.lib[ \t]+\S+|include[ \t]+cap_cmomf\.lib)[ \t]*$',
            '* Simulator model, not circuit hierarchy', source.read_text()))
    top = design.readFromSpice(str(circuit), args.cell)
    if libraries:
        for name in libraries:
            order = re.search(r'^\.subckt ' + name + r' ([^\n]+)', source.read_text(), re.M)[1].split()
            if order != provider.canonical_port_order(name):
                raise ValueError(f'{name}: saved Magic port order differs from fresh schematic')
        if args.cell == 'ring_oscillator':
            ring.place_and_route(top, provider, shield_feedback=args.shield_feedback,
                                 local_interstage=args.local_interstage)
        else:
            analog.place_and_route(top, provider)
    elif args.cell == 'loop_filter':
        loop_filter.place_and_route(top, provider)
    elif args.cell == 'charge_pump':
        charge_pump.place(top, provider)
        charge_pump.route(top, provider.metadata)
    elif args.cell in ('inverter', 'vco_buffer'):
        inverter.place(top, provider, args.cell, row_pitch=row_pitch)
        inverter.route(top, provider.metadata, args.cell, row_pitch=row_pitch)
    else:
        x = 0
        for device in top.ckt.instances:
            placed = top.addInstance(device, x, 0)
            data = provider.metadata[device.name]
            data['translation'] = [int(placed.x1) - data['bounds'][0],
                                   int(placed.y1) - data['bounds'][1]]
            x = int(placed.x2) + 50000
        top.updateBoundingRect()
        route_bias(top, provider.metadata)
        top.updateBoundingRect()
    cic.MagicPrinter(str(output), rules).print(design)
    manifest = {'cell': args.cell, 'stage': f'routed {args.cell} experiment; NOT signoff',
                'inverter_row_pitch_um': args.inverter_row_pitch_um,
                'schematic_library': str(schematic), 'sizing_overrides': args.set_size,
                'source': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'circuit_input': str(circuit),
                'circuit_input_sha256': hashlib.sha256(circuit.read_bytes()).hexdigest(),
                'recipe_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'charge_pump_recipe_sha256': hashlib.sha256(Path(charge_pump.__file__).read_bytes()).hexdigest(),
                'inverter_recipe_sha256': hashlib.sha256(Path(inverter.__file__).read_bytes()).hexdigest(),
                'loop_filter_recipe_sha256': hashlib.sha256(Path(loop_filter.__file__).read_bytes()).hexdigest(),
                'schematic_sha256': hashlib.sha256((schematic / f'{args.cell}.sch').read_bytes()).hexdigest(),
                'pdk_fet_generator_sha256': hashlib.sha256(
                    (RC.parent / 'ihp-sg13cmos5l-fet.tcl').read_bytes()).hexdigest(),
                'pdk_passive_generators_sha256': {
                    kind: hashlib.sha256((RC.parent / f'ihp-sg13cmos5l-{kind}.tcl').read_bytes()).hexdigest()
                    for kind in ('res', 'cap')},
                'cic_module': cic.__file__,
                'devices': provider.metadata}
    if libraries:
        manifest.update(leaf_inputs_sha256=provider.hashes,
                        shield_feedback=args.shield_feedback,
                        local_interstage=args.local_interstage,
                        ring_recipe_sha256=hashlib.sha256(Path(ring.__file__).read_bytes()).hexdigest(),
                        analog_recipe_sha256=hashlib.sha256(Path(analog.__file__).read_bytes()).hexdigest())
        # The CIC assembly references the preserved leaf .mag library beside
        # it; it is not a standalone process-device database.
        (output / f'{args.cell}.cic').write_text(json.dumps(design.toJson(), indent=2) + '\n')
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Generated {output}; {manifest["stage"]}; not integration-ready')


if __name__ == '__main__':
    main()
