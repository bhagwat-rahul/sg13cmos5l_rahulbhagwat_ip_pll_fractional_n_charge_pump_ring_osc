#!/usr/bin/env python3
"""Package checked core views and an unconnected slot13 placement draft.

Run with container python3 (KLayout enabled). Never installs a submission or
modifies the harness. The checked GDS, not a raw Magic re-export, is packaged
so readonly digital polygons and CMOM recognition annotations survive.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

import klayout.db as db

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked(report, required):
    summary = json.loads((report / 'summary.json').read_text())
    for gate in required:
        if summary[gate]['status'] != 'PASS':
            raise ValueError(f'{report}: required physical gate failed: {gate}')
    inputs = json.loads((report / 'inputs.json').read_text())
    for name, digest in inputs.items():
        if sha(report / 'mag' / name) != digest:
            raise ValueError(f'changed checker snapshot: {name}')
    stream = report / 'pll_core.gds'
    if sha(stream) != json.loads((report / 'cmom_annotations.json').read_text())['annotated_sha256']:
        raise ValueError('checked stream changed')
    return stream


def copy_library(source, target):
    target.mkdir(parents=True)
    for path in source.iterdir():
        if path.suffix not in ('.mag', '.gds'):
            continue
        if path.suffix == '.gds':
            shutil.copy2(path, target / path.name)
            continue
        text = path.read_text()
        for backing in set(re.findall(r'^string GDS_FILE (.+)$', text, re.M)):
            name = Path(backing).name
            if not (source / name).is_file():
                raise ValueError(f'missing readonly backing stream: {backing}')
            text = text.replace(f'string GDS_FILE {backing}\n',
                                f'string GDS_FILE {target / name}\n')
        (target / path.name).write_text(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unfilled-report', type=Path, required=True)
    parser.add_argument('--filled-report', type=Path, required=True)
    parser.add_argument('--fill-keepouts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or not output.is_relative_to(ROOT / 'layout/build'):
        parser.error('output must be a NEW directory under layout/build')
    unfilled, filled = args.unfilled_report.resolve(), args.filled_report.resolve()
    gates = ['lvs-magic', 'lvs-klayout']
    streams = [checked(unfilled, gates), checked(filled, gates + [
        'drc-magic', 'drc-klayout-full', 'antenna-magic', 'gds-physical-roundtrip'])]
    # This package is for the maintained compact assembly, not an old snapshot.
    inputs = json.loads((unfilled / 'inputs.json').read_text())
    for name, digest in inputs.items():
        source = ROOT / 'layout/core/mag' / name
        if source.suffix == '.gds':
            source = ROOT / 'layout/core/mag/pll_digital.gds'
        if not source.is_file():
            raise ValueError(f'missing maintained source: {name}')
        if sha(source) != digest:
            # Checker snapshots relocate readonly GDS_FILE paths only.
            if source.suffix != '.mag' or re.sub(r'^string GDS_FILE .+$', '', source.read_text(), flags=re.M) != re.sub(
                    r'^string GDS_FILE .+$', '', (unfilled / 'mag' / name).read_text(), flags=re.M):
                raise ValueError(f'maintained source differs: {name}')
    harness = ROOT.parent / 'sg13cmos5l_ocd_chipalooza'
    wrapper = harness / 'magic/slot13_wrapper.mag'
    wrapper_gds = harness / 'gds/slot13_wrapper.gds'
    text = wrapper.read_text()
    if not re.search(r'^magscale 1 2$', text, re.M) or not re.search(
            r'^string FIXED_BBOX 0 0 107430 54600$', text, re.M):
        raise ValueError('review changed slot13 boundary')
    slot_bounds = db.DBox(0, 0, 537.15, 273)
    output.mkdir(parents=True)
    audits = {}
    for variant, report, stream in zip(('unfilled', 'filled'), (unfilled, filled), streams):
        directory = output / variant
        mag = directory / 'mag'
        copy_library(report / 'mag', mag)
        bounds = re.search(r'^string FIXED_BBOX (.*)$', (mag / 'pll_core.mag').read_text(), re.M)[1]
        (mag / 'slot_13.mag').write_text(
            'magic\ntech ihp-sg13cmos5l\nmagscale 1 2\ntimestamp 0\n'
            'use pll_core Xpll\ntransform 1 0 0 0 1 0\nbox ' + bounds + '\n'
            '<< properties >>\nstring FIXED_BBOX 0 0 107430 54600\n<< end >>\n')
        (mag / 'slot13_interface_preview.mag').write_text(text)
        (mag / 'slot13_preview.mag').write_text(
            'magic\ntech ihp-sg13cmos5l\nmagscale 1 2\ntimestamp 0\n'
            'use slot_13 Xslot\ntransform 1 0 0 0 1 0\nbox 0 0 107430 54600\n'
            'use slot13_interface_preview Xinterface\ntransform 1 0 0 0 1 0\nbox 0 0 107430 54600\n'
            '<< properties >>\nstring FIXED_BBOX 0 0 107430 54600\n<< end >>\n')
        gds = directory / 'gds'
        gds.mkdir()
        shutil.copy2(stream, gds / 'pll_core.gds')
        layout = db.Layout()
        layout.read(str(stream))
        core = layout.cell('pll_core')
        if (core.dbbox() & slot_bounds) != core.dbbox():
            raise ValueError(f'{variant} stream exceeds slot: {core.dbbox()}')
        slot = layout.create_cell('slot_13')
        slot.insert(db.CellInstArray(core.cell_index(), db.Trans()))
        slot.shapes(layout.layer(189, 4)).insert(db.Box.from_dbox(slot_bounds * (1 / layout.dbu)))
        options = db.SaveLayoutOptions()
        options.select_cell(slot.cell_index())
        layout.write(str(gds / 'slot_13.gds'), options)
        reread = db.Layout()
        reread.read(str(gds / 'slot_13.gds'))
        if [c.name for c in reread.top_cells()] != ['slot_13']:
            raise ValueError('wrong slot stream top')
        placed = list(reread.cell('slot_13').each_inst())
        if (len(placed) != 1 or placed[0].cell.name != 'pll_core'
                or placed[0].trans != db.Trans()):
            raise ValueError('wrong core placement in slot')
        pairs = {(i.layer, i.datatype) for l in (layout, reread) for i in l.layer_infos()}
        for layer in pairs:
            before = db.Region(core.begin_shapes_rec(layout.layer(*layer)))
            after = db.Region(reread.cell('pll_core').begin_shapes_rec(reread.layer(*layer)))
            if not (before ^ after).is_empty():
                raise ValueError(f'packaging changed core polygons: {layer}')
        # Overlay is a review artifact only: the real harness already owns
        # these interface shapes. Never install this preview as a user macro.
        interface = db.Layout()
        interface.read(str(wrapper_gds))
        if interface.dbu != layout.dbu:
            raise ValueError('review wrapper/core stream grid conversion')
        copied = layout.create_cell('slot13_interface_preview')
        copied.copy_tree(interface.cell('slot13_wrapper'))
        preview = layout.create_cell('slot13_preview')
        for child in (slot, copied):
            preview.insert(db.CellInstArray(child.cell_index(), db.Trans()))
        options.select_cell(preview.cell_index())
        layout.write(str(gds / 'slot13_preview.gds'), options)
        audits[variant] = dict(report=str(report.relative_to(ROOT)),
            checked_stream_sha256=sha(stream), core_polygon_xor='empty',
            packaged_gds_sha256={p.name: sha(p) for p in gds.glob('*.gds')},
            core_bounds_um=str(core.dbbox()), slot_origin_um=[0, 0],
            slot_bounds_um=[0, 0, 537.15, 273],
            source_summary=json.loads((report / 'summary.json').read_text()))
    shutil.copy2(args.fill_keepouts, output / 'fill_keepouts.gds')
    (output / 'manifest.json').write_text(json.dumps(dict(
        stage='UNCONNECTED PLACEMENT DRAFT; NOT SUBMISSION',
        recipe_sha256=sha(Path(__file__)), fill_keepouts_sha256=sha(args.fill_keepouts),
        harness_wrapper_sha256=sha(wrapper), harness_wrapper_gds_sha256=sha(wrapper_gds),
        variants=audits, pin_connections_complete=False,
        limitations=['No core-to-harness pin routing or reset-polarity adapter',
                     'Harness still has analog pads; dedicated clock pad changes pending',
                     'Slot wrapper LVS, full RC, post-fill performance and full-chip signoff pending']), indent=2) + '\n')
    (output / 'README.md').write_text('''# Slot13 placement draft — NOT SUBMISSION

Both variants contain `mag/` (complete editable library plus readonly digital
backing GDS) and `gds/pll_core.gds` (exact checked stream). `gds/slot_13.gds`
has the harness-required top name and origin, with the core instantiated at
(0,0) inside the 537.15 × 273 µm slot. It adds only the slot boundary, no routes.
`slot13_preview` in Magic/GDS overlays existing harness access shapes for review;
do NOT install the preview as a project (the harness already owns those shapes).

**Not electrically connected to the harness.** Supplies, config, enable/reset,
bias and dedicated clocks still need wrapper routing; clock pads are still
analog in the current harness. No slot-level LVS or electrical pass is claimed.
The manifest preserves checker results, including known PEX failures.

Use unfilled for wrapper routing and later full-chip fill. Filled is a checked
core-density reference only; recheck density and parasitics after integration.
`fill_keepouts.gds` is fill-generation metadata, not submission paint.
Magic backing-stream paths resolve inside this package; rerun packaging if moved.
Nothing has been copied into the harness or installed in final/gds.
''')
    print(output)


if __name__ == '__main__':
    main()
