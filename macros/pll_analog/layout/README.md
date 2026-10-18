# Analog layout starting cells

`mag/` contains the initial SG13CMOS5L Magic device geometry and circuit
hierarchy generated from `../netlist/magic-import/*.spice` using Magic
8.3.681 and the installed `ihp-sg13cmos5l` device generators. No old analog
layout was reused. This is an **unrouted starting point**, not an LVS/DRC-clean
analog macro.

## Open in the tools container

From the PLL-only repository root:

```sh
source .designinit
cd macros/pll_analog/layout/mag
magic -rcfile "$PDKPATH/libs.tech/magic/ihp-sg13cmos5l.magicrc" pll_analog.mag
```

Expand the hierarchy with `select top cell` followed by `expand` in the Magic
console. Individual circuit cells can also be opened directly.

| Circuit cell | Direct instances |
| --- | ---: |
| `inverter` | 4 |
| `vco_bias` | 2 |
| `vco_buffer` | 4 |
| `charge_pump` | 9 |
| `loop_filter` | 3 |
| `ring_oscillator` | 5 |
| `pll_analog` | 3 |

There are 24 `.mag` files: seven circuit cells and 17 generated primitive
cells. Keep the primitive files with the circuit files; they contain the
actual transistor, resistor, and capacitor geometry. Identical devices can
share a generated cell, so editing shared geometry affects every instance
of that cell. The three oscillator stages also intentionally share the
`inverter` circuit cell.

## What still needs doing

- Device placement, matching, orientation, and any required guard structures.
- All inter-device wiring, including multifinger gate connections: the MOS
  generators currently have `conn_gates=0`.
- Well/substrate ties and supply routing appropriate to the final placement.
- Replace/move the importer's placeholder metal1 circuit ports and connect
  them to the actual nets. Their present positions are not a pin plan.
- DRC, schematic LVS, and PEX followed by post-layout simulation.

The import files use their own internally consistent subcircuit port order;
newer Xschem exports may list those ports in a different order. Match nets by
name, and use a fresh schematic export for LVS, not these import-only decks.

The initial save emitted out-of-date timestamp and unnamed-cell warnings.
A separate fresh Magic session successfully loaded and expanded the complete
saved hierarchy without missing-child or timestamp errors. Direct instance
counts match the table above; device parameters retain the requested finger
counts and the capacitors use metal2 through metal4. This is a file/hierarchy
check only, not physical sign-off.

Do not rerun SPICE import over these files once manual layout starts. Use a
new directory if another initial import is needed.

## One-command checks

Inside IIC-OSIC-TOOLS, from this directory (`macros/pll_analog/layout`):

```sh
make check charge_pump    # all checks for one cell
make check pll_analog     # analog top, including its placed hierarchy
make check               # defaults to pll_analog
make check-all           # every circuit cell in the table above, plus analog top
```

The runner selects **ihp-sg13cmos5l** explicitly, even if the container defaults
to another PDK. Save all Magic and Xschem edits first: checks read the on-disk
files, not unsaved GUI state. Run from `layout/`, not `layout/mag/`.

Individual check modes are also available:

```sh
make drc vco_bias          # Magic full DRC on the .mag hierarchy
make drc-klayout vco_bias  # full installed KLayout deck, including antenna
make drc-all vco_bias      # both DRC engines
make antenna vco_bias      # Magic antenna + KLayout antenna-only deck
make lvs vco_bias          # Magic/Netgen and KLayout LVS
make pex vco_bias          # flattened coupled R+C extraction and port check
make gds-roundtrip vco_bias # GDS reimport, then Magic DRC/antenna/LVS/PEX
# Equivalent direct script interface:
python3 run_checks.py all charge_pump
```

`check` runs these independent checks, continuing after failures:

| Check | Coverage |
| --- | --- |
| Input hierarchy | Missing/empty cells and wrong Magic technology fail before tools run |
| Magic DRC | `drc(full)`, Euclidean checking, waits for DRC completion |
| KLayout DRC | Entire installed main deck, antenna, density, and maximal/extra rules; no macro/precheck exclusions |
| Magic antenna | Extracted hierarchy antenna checking, with reloadable feedback |
| Magic/Netgen LVS | Fresh schematic SPICE versus extraction from the `.mag` files |
| KLayout LVS | Fresh schematic CDL versus the automatically exported layout |
| PEX | Flattened layout, full interconnect resistance plus original-node lumped ground/coupling C; explicit `extresist all`, 0 mΩ extraction threshold, 1 mΩ simplification, no delay filtering, 0 capacitance output threshold; port-fragment validation |
| GDS round-trip | Reimport exported GDS into an empty Magic working library, save its hierarchy, then rerun Magic full DRC, antenna, schematic LVS and the same extraction/port checks on that serialized geometry |

The LVS reference copies omit only the loop filter's simulator-only
`cornerRES.lib` and `cap_cmomf.lib` directives: device definitions come from
the PDK LVS setup. Raw Xschem exports are retained alongside those copies;
arbitrary circuit includes are not removed. Extraction errors, orphaned-node
warnings, and shorted-port warnings fail PEX rather than producing a pass.

`.mag` is the only maintained layout input. Each invocation copies the saved
layout library into a new `build/<cell>/<timestamp>/mag/` snapshot. KLayout
cannot read Magic files, so its checks use a GDS generated from that snapshot;
no manual GDS export or separate GDS source is required. The source `.mag`
files and normal schematic netlists are not overwritten.

For native `cap_cmomf` cells with M4 as their top metal, export supplies the
CMOS5L LVS recognition purpose (99/40) and M4 pin-purpose shapes (50/2).
These come from saved native PCell bounds/labels, not schematic nets. Pin
shapes must lie on physical M4 and inside the device body; other top-metal
stacks are rejected pending a reviewed mapping. An empty physical-layer XOR
is required. The untouched stream is retained as `<cell>.raw-magic.gds`, and
`cmom_annotations.json` records source hashes, geometry, output hashes and
limitations. This allows KLayout device recognition, not capacitance-value
verification or native Magic LVS/PEX closure. The current Magic technology
does not import 99/40. The round-trip checker therefore retains that purpose
in a lossless hierarchical `gds-import/recognition.gds` sidecar and imports
the remaining stream into an empty Magic library. Pin purpose 50/2 stays in
the import: removing it loses real circuit ports. The actual Magic reexport
must have an empty non-99/40 polygon XOR against the original annotated
stream. Only then is recognition restored to corresponding cells in that
reexport; both physical and recognition polygon XORs are rechecked after
serialization. `physical_xor.json` records hashes and differences. KLayout
LVS runs on this restored reexport as an additional check. A changed-metal
negative control is rejected before LVS. No installed PDK files are modified.

`gds-physical-roundtrip: PASS` establishes serialization/recognition polygon
preservation, not extraction qualification. The overall `gds-roundtrip` gate
still fails when reimported native CMOM LVS or resistor-body PEX fails;
restored recognition is never used to invent native Magic capacitor devices
or waive missing capacitance endpoints.

`check` also includes the GDS round-trip gate. The import runs without loading
any source `.mag`, so it cannot silently reuse the original geometry. Its
fresh report directory is linked from the parent summary and contains the
GDS SHA256/provenance, imported-layout hashes, per-check results and another
`pex/<cell>_pex.spice`. The original GDS still receives KLayout DRC/LVS;
reimport is an additional serialization/extraction check, not a replacement.
It uses the same Magic extraction engine and lumped-C approximation described
below, **not independent or foundry-qualified PEX**. Different resistor mesh
counts after GDS retiling do not alone imply changed effective resistance;
compare electrical results before substituting an extracted netlist.

Each run prints its report directory and writes `summary.txt`, `summary.json`,
input SHA256 hashes, per-tool logs, Magic DRC coordinates, KLayout `.lyrdb`
markers, LVS reports/databases, antenna feedback, and the PEX netlist
`pex/<cell>_pex.spice`. Generated `build/` contents are Git-ignored. Exit status
is nonzero if any requested check fails. Missing reports/tool errors also fail;
an incomplete KLayout run is not accepted as a clean result.

The PEX export explicitly disables hierarchy after the LVS preset: Magic
8.3.681's hierarchical exporter incorrectly applies resistor-π capacitance
movement to MOS subcircuits. It also saves `<cell>_c_only.spice` before
resistance annotation. Because extresist adds grounded copies of coupling C,
the final PEX uses that independent C-only matrix at the original named nodes,
retaining the full resistance network and device terminal connections.
Missing or shorted capacitor endpoints fail the check. The untouched resistance
export is retained as `<cell>_raw_extresist.spice`; `capacitance_model.json`
records the approximation. **C is lumped at original nodes, not spatially
distributed along resistance fragments.** This is not foundry-qualified PEX
or a substrate-noise model. Earlier results using the old hierarchical/duplicated
capacitance export must be regenerated before electrical conclusions are used.

`pex/capacitance_endpoint_audit.json` records missing original C endpoints,
their affected capacitor lines and the reference/resistance-export hashes.
The current filter fails on the internal `rhigh` body node. PEX explicitly
keeps resistor tee off: the installed flat tee emitter loses the second half,
and hierarchical tee changes the foundry model's contact/capacitance behavior.
Do not remove the affected C or split the model just to pass this audit.
See `../cic/README.md` for the reproduced tool failure and electrical control.

Magic can exit zero after reporting an undefined layer, ambiguous CIF style,
or nonzero output problems. These diagnostics now fail the check regardless
of its final completion marker. In particular the installed CMOS5L pattern-fill
style references undefined `dnwell`; its output is not accepted as valid fill.

**Interpretation:** a PEX pass means extraction and the port-fragment check
completed, not that LVS, functionality, analog performance, or all port DC
connections are correct. Resistance extraction can legitimately omit nets
without a device current path. Use the separate LVS results and post-layout
simulation before relying on PEX. The unrouted initial imports are expected
to fail DRC/LVS, and chip-level density/boundary rules may fail on an isolated
block. No rules are waived to make those blocks pass.

This is comprehensive verification against the **installed open PDK decks**,
not a guarantee of foundry signoff. Repeat checks on the integrated chip and
confirm the MPW's required decks, density/fill treatment, and acceptance rules.
