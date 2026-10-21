#!/usr/bin/env python3
"""CIC assembly of maintained analog + frozen digital, including its /2.

Run with /opt/ciccreator/.venv/bin/python inside IIC-OSIC-TOOLS. Outputs
are disposable candidates, never changes to either input macro or the MPW
wrapper. No fill, pads, added prescaler, or timing/EM/ESD qualification.
"""

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

import cicpy as cic

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'macros/pll_analog/cic'))
sys.path.insert(0, str(ROOT / 'scripts'))
from ring import Leaves
from check_pex_ports import subcircuits

PDK = Path('/foss/pdks/ihp-sg13cmos5l')
FROZEN = ROOT / 'macros/pll_digital/frozen/v1'
ANALOG = ROOT / 'macros/pll_analog/layout/mag'
SOURCE = ROOT / 'schematic/pll_core.spice'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output, name, args, cwd=None):
    with (output / f'{name}.log').open('w') as log:
        subprocess.run(list(map(str, args)), cwd=cwd or output,
                       stdout=log, stderr=subprocess.STDOUT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'layout/build'):
        parser.error('output must be under layout/build/')
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        parser.error('output must be empty; retain previous candidates')
    for line in (FROZEN / 'SHA256SUMS').read_text().splitlines():
        expected, name = line.split(maxsplit=1)
        if sha(FROZEN / name) != expected:
            raise ValueError(f'frozen digital package changed: {name}')
    inputs = {str(p.relative_to(ROOT)): sha(p) for p in ANALOG.glob('*.mag')}
    inputs.update({str(p.relative_to(ROOT)): sha(p) for p in
                   (SOURCE, Path(__file__), FROZEN / 'SHA256SUMS',
                    FROZEN / 'gds/pll_digital.gds', FROZEN / 'lef/pll_digital.lef',
                    FROZEN / 'pnl/pll_digital.pnl.v')})
    declarations = {name: ports for name, ports, _ in subcircuits(SOURCE)}
    lef = (FROZEN / 'lef/pll_digital.lef').read_text()
    if re.search(r'SIZE\s+160\.000 BY 140\.000', lef) is None:
        raise ValueError('review placement for changed digital boundary')
    pins = {}
    for name, body in re.findall(r'  PIN (\S+)\n(.*?)  END \1\n', lef, re.S):
        shapes = []
        for layer, rectangle in re.findall(r'LAYER Metal([234])\s*;\s*RECT ([^;]+);', body):
            shapes.append(('M' + layer, [float(v) for v in rectangle.split()]))
        if not shapes:
            raise ValueError(f'no supported LEF access for {name}')
        pins[name] = shapes
    if set(pins) != set(declarations['pll_digital']):
        raise ValueError('digital LEF and circuit declaration pins differ')

    imported = output / 'digital'
    imported.mkdir()
    script = output / 'import_digital.tcl'
    script.write_text(f'''crashbackups stop
drc off
gds readonly true
gds flatten false
gds flatglob none
gds read {{{FROZEN / 'gds/pll_digital.gds'}}}
load pll_digital
select top cell
writeall force
puts DIGITAL_IMPORTED
quit -noprompt
''')
    run(output, 'import_digital', ['magic', '-dnull', '-noconsole', '-rcfile',
        PDK / 'libs.tech/magic/ihp-sg13cmos5l.magicrc', script], imported)
    log = (output / 'import_digital.log').read_text()
    if 'DIGITAL_IMPORTED' not in log or re.search(
            r'(?im)^Error|Unknown layer/datatype|Unrecognized layer|[1-9]\d* problems occurred', log):
        raise RuntimeError('incomplete digital import; see import_digital.log')
    if any('<< metal5 >>' in p.read_text() for p in imported.glob('*.mag')):
        raise ValueError('M5 macro obstruction requires a new routing plan')
    path = imported / 'pll_digital.mag'
    text = path.read_text()
    scale = re.search(r'^magscale (\d+) (\d+)$', text, re.M)
    unit = Fraction(int(scale[1]), 100 * int(scale[2]))

    def native(value):
        coordinate = Fraction(str(value)) / unit
        if coordinate.denominator != 1:
            raise ValueError(f'off-grid LEF access: {value}')
        return str(int(coordinate))

    # GDS text is not a numbered Magic port. Add numbered LEF accesses to
    # the interpreted view, retaining GDS_FILE/START/END for raw streamout.
    # Regenerating frozen cells from Magic paint changes their implants.
    labels = []
    for index, name in enumerate(declarations['pll_digital'], 1):
        for layer, shape in pins[name]:
            labels += [f'rlabel metal{layer[-1]} s ' + ' '.join(map(native, shape)) + f' 0 {name}',
                       f'port {index} nsew signal bidirectional']
    text = re.sub(r'^<< labels >>\n.*?(?=^<< )', '', text, flags=re.M | re.S)
    text = text.replace('<< properties >>', '<< labels >>\n' + '\n'.join(labels)
                        + '\n<< properties >>') if '<< properties >>' in text else text.replace(
                            '<< end >>', '<< labels >>\n' + '\n'.join(labels) + '\n<< properties >>\n<< end >>')
    text = re.sub(r'^string FIXED_BBOX .*\n', '', text, flags=re.M)
    text = text.replace('<< properties >>\n', '<< properties >>\nstring FIXED_BBOX 0 0 '
                        + native(160) + ' ' + native(140) + '\n')
    path.write_text(text)

    library = output / 'mag'
    library.mkdir()
    technology = dict(version=2, technology=dict(gamma=50, grid=5, techlib='ihp-sg13cmos5l'),
                      rules={'CELL': {'space': 1000}}, layers={'PR': dict(alias='', number=0, material='pnr')})
    for n in range(1, 6):
        technology['layers'][f'M{n}'] = dict(alias=f'metal{n}', number=n, material='metal')
        if n < 5:
            technology['layers'][f'VIA{n}'] = dict(alias=f'via{n}', number=10+n,
                material='cut', previous=f'M{n}', next=f'M{n+1}')
    tech = output / 'routing.tech'
    tech.write_text(json.dumps(technology, indent=2) + '\n')
    rules = cic.Rules(str(tech))
    design = cic.MagicDesign('ihp-sg13cmos5l', rules)
    provider = Leaves({'pll_analog': ANALOG, 'pll_digital': imported}, library)
    design.registerPrimitiveProvider(provider)
    for cell in ('pll_analog', 'pll_digital'):
        if declarations[cell] != provider.canonical_port_order(cell):
            raise ValueError(f'{cell}: source declaration differs from numbered physical ports')
    top = design.readFromSpice(str(SOURCE), 'pll_core')
    # Coordinates in um; CIC's database is 10,000 units/um. Analog retains
    # its negative-coordinate origin; the actual translated bounds are
    # x=18..415.2, y=20..299 um. Digital bounds x=455..615, y=160..300.
    placements = {'Xanalog': (18, 20), 'Xdigital': (455, 160)}
    endpoints = {}
    for instance in top.ckt.instances:
        x, y = placements[instance.name]
        placed = top.addInstance(instance, round(x*10000), round(y*10000))
        data = provider.metadata[instance.name]
        dx = int(placed.x1) - data['bounds'][0]
        dy = int(placed.y1) - data['bounds'][1]
        for pin in declarations[instance.subcktName]:
            entry = data['pins'][pin]
            a, b, c, d = entry['shape']
            endpoints[instance.name, pin] = (entry['layer'], (dx+(a+c)//2)/10000,
                                            (dy+(b+d)//2)/10000)

    def rect(layer, x1, y1, x2, y2):
        return cic.Rect(layer, round(x1*10000), round(y1*10000),
                        round((x2-x1)*10000), round((y2-y1)*10000))

    def wire(layer, points, width=.4):
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            if x1 != x2 and y1 != y2:
                raise ValueError('non-Manhattan top route')
            top.add(rect(layer, min(x1,x2)-width/2, min(y1,y2)-width/2,
                         max(x1,x2)+width/2, max(y1,y2)+width/2))

    def via(level, x, y):
        width, cut = (2., .62) if level == 4 else (.4, .2)
        for n in (level, level+1):
            landing = .8 if level == 4 and n == 4 else width
            top.add(rect(f'M{n}', x-landing/2, y-landing/2, x+landing/2, y+landing/2))
        top.add(rect(f'VIA{level}', x-cut/2, y-cut/2, x+cut/2, y+cut/2))

    def access(instance, pin, metal):
        layer, x, y = endpoints[instance, pin]
        for n in range(int(layer[-1]), metal):
            via(n, x, y)
        return x, y

    def port(name, layer, x, y, width=.4):
        top.addPortFromRect(name, rect(layer, x-width/2, y-width/2, x+width/2, y+width/2))

    # The critical clock stays in the clear inter-macro channel on M3/M4.
    ax, ay = access('Xanalog', 'VCO_CLK', 3)
    dx, dy = access('Xdigital', 'vco_clk', 3)
    wire('M3', [(ax,ay), (435,ay)])
    via(3,435,ay)
    wire('M4', [(435,ay), (435,dy)])
    via(3,435,dy)
    wire('M3', [(435,dy), (dx,dy)])
    # Nested upper-metal routes avoid crossing one another. No routing on
    # occupied M1-M4 inside either macro except their actual access shapes.
    for pin, rail_y, escape_x in [('UP',310,635), ('DOWN',320,645)]:
        ax, ay = access('Xanalog', pin, 5)
        dx, dy = access('Xdigital', pin.lower(), 3)
        wire('M3', [(dx,dy), (escape_x,dy)])
        via(3,escape_x,dy)
        via(4,escape_x,dy)
        wire('M5', [(ax,ay), (ax,rail_y), (escape_x,rail_y), (escape_x,dy)], 2.)
    # Wide common entry rails, separate macro branches, and ALL three
    # digital access straps per supply. Via arrays, not single power cuts.
    for net, rail_y in [('VDD',330), ('VSS',350)]:
        ax, ay = access('Xanalog', net, 4)
        branches = [(ax,ay)] + [(455+(r[0]+r[2])/2, 160+r[3]) for _,r in pins[net]]
        for x,y in branches:
            wire('M4', [(x,y), (x,rail_y+1.5)], 1. if x>=455 else 4.)
            # One column, three TopVia1 cuts (1-um pitch) at the entry.
            for oy in (-1.,0.,1.):
                via(4,x,rail_y+oy)
        wire('M5', [(0,rail_y), (max(x for x,_ in branches),rail_y)], 10.)
        port(net,'M5',0,rail_y,10.)
    ax, ay = access('Xanalog','IREF',3)
    wire('M3', [(ax,ay),(0,ay)])
    port('IREF','M3',0,ay)
    for pin, track in [('ref_clk',425), ('reset_n',430), ('enable',440)]:
        x,y = access('Xdigital',pin,3)
        wire('M3',[(x,y),(track,y)])
        port(pin,'M3',track,y)
    for pin in pins:
        if pin.startswith(('div_ratio[','test_div_select[')):
            x,y = access('Xdigital',pin,4)
            # Local boundary accesses avoid long, unprotected input antennas.
            # Pad-level routing must recheck antenna against its added length.
            wire('M4',[(x,y),(x,303)])
            port(pin,'M4',x,303)
    x,y = access('Xdigital','test_clk',3)
    wire('M3',[(x,y),(660,y)])
    port('clk_out','M3',660,y)
    top.updateBoundingRect()
    cic.MagicPrinter(str(library), rules).print(design)
    (output / 'interface.json').write_text(json.dumps({
        'ports': declarations['pll_core'], 'endpoints_um': {str(k):v for k,v in endpoints.items()},
        'digital_power_shapes_um': {n:pins[n] for n in ('VDD','VSS')},
        'prescaler': 'frozen digital includes fixed /2; no extra prescaler',
        'unrouted_observation_ports': ['pll_clk','feedback_clk'],
        'limitations': 'provisional core only; no pads/fill or electrical qualification'
    }, indent=2)+'\n')
    if any(sha(ROOT / name) != digest for name,digest in inputs.items()):
        raise RuntimeError('an input changed during generation')
    (output / 'manifest.json').write_text(json.dumps({'stage':'provisional integration, NOT signoff',
        'inputs_sha256':inputs, 'library':str(library), 'source':str(SOURCE)},indent=2)+'\n')
    print(f'Generated {library / "pll_core.mag"}')


if __name__ == '__main__':
    main()
