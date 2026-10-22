# Analog Magic integration baseline — no density fill

`mag/` is the maintained **routed, non-density-filled** `ihp-sg13cmos5l`
analog hierarchy, promoted from CIC candidate `build/cic-analog-pulse-031`.
It is a **provisional integration baseline, not a signoff freeze**. Place
`pll_analog` beside the frozen digital/prescaler macro, complete top routing
and power planning, then generate context-aware density fill and requalify.

The 27 Magic files retain that non-filled candidate's geometry. The two
CMOM cells now have explicit `cap_cmomf` model-view device properties instead
of the native generator's ideal-capacitor properties; dimensions and stack
come from their saved PCell metadata. No mask geometry or ports changed.
Functional device guards, well/substrate contacts, signal routing, supplies
and pin access are retained. The separate density-only
`cic_analog_metal_fill` cell/reference is absent. This promotion does not
compact the floorplan, redesign the PDN or include the digital macro.

The matching maintained Xschem sizes are inverter M1–M4 W =
18.0/3.6/3.6/18.0 µm and buffer M1–M4 W = 2.40/1.80/1.80/0.90 µm;
lengths and finger counts are unchanged. The affected ordinary schematic
SPICE exports are regenerated. Use these maintained schematics for fresh
LVS; the old `netlist/magic-import/` decks describe the initial import only.

The filled experiment remains separate at `build/cic-analog-pulse-feol-031`.
Its electrical results are not automatically qualification of the non-filled
or integrated layout. See `../cic/README.md` for recipe history and limitations.

## Open in the tools container

From the PLL-only repository root:

```sh
source .designinit
cd macros/pll_analog/layout/mag
magic -rcfile "$PDKPATH/libs.tech/magic/ihp-sg13cmos5l.magicrc" pll_analog.mag
```

Expand the hierarchy with `select top cell` followed by `expand` in the Magic
console. Individual circuit cells can also be opened directly.

To instantiate it from a different Magic working directory, add the complete
library to Magic's search path and then place the top cell:

```tcl
# Substitute the absolute container path to this repository.
path search +/foss/designs/current-designs/chipalooza2/sg13cmos5l_rahulbhagwat_ip_pll_fractional_n_charge_pump_ring_osc/macros/pll_analog/layout/mag
# Set the box lower-left to the desired placement point (example: origin).
box values 0 0 0 0
getcell pll_analog
```

Use the same technology startup file for the integration layout. Keep all
child cells available; copying only `pll_analog.mag` does not copy its devices.
The ports are VDD, VSS, UP, DOWN, IREF and VCO_CLK; connect by name. Guard
rings are functional structures, not density fill or qualified ESD clamps.
This workflow was tested from a separate working directory: the exported
scratch wrapper contains `pll_analog` and all 27 maintained hierarchy cells.

| Circuit cell | Direct instances |
| --- | ---: |
| `inverter` | 4 |
| `vco_bias` | 2 |
| `vco_buffer` | 4 |
| `charge_pump` | 9 |
| `loop_filter` | 3 |
| `ring_oscillator` | 5 |
| `pll_analog` | 3 |

There are 27 `.mag` files: seven circuit cells and 20 generated primitive
cells. Keep the primitive files with the circuit files; they contain the
actual transistor, resistor, and capacitor geometry. Identical devices can
share a generated cell, so editing shared geometry affects every instance
of that cell. The three oscillator stages also intentionally share the
`inverter` circuit cell.

## What still needs doing

- Analog/digital placement and inter-macro signal/supply routing, including
  supply-entry planning, isolation clearances and pad/ESD compatibility.
- PDN IR-drop/current-density/dynamic-noise qualification; current straps
  and guards are not a power-integrity signoff claim.
- Final context-aware fill and integrated DRC/LVS/antenna/density closure.
- Full RC extraction/model closure and GDS-import passive-model handling, followed by
  integrated electrical/PVT/acquisition/noise qualification.

Promotion check `build/pll_analog/20261018-234516-896361` uses the default
maintained layout and schematic paths: Magic full DRC and antenna pass,
independent GDS LVS passes, and physical/recognition round-trip XOR is empty.
Full KLayout DRC reports exactly seven density categories: AFil.g, GFil.g,
M1.j, M2.j, M3.j, M4.j and TM1.c. Native Magic CMOM LVS and rhigh-body PEX
still fail. Thus `make check pll_analog` returns nonzero; no rule is waived.

The subsequent capacitor model-view correction makes maintained-source
Magic/Netgen LVS pass for all seven circuit cells, alongside independent
GDS LVS. Magic now extracts hierarchy before Netgen flattens the circuit,
preserving PCell model properties. This is **model-view LVS**, not new native
geometric CMOM recognition. The GDS-reimported Magic library still lacks
these properties, so that native round-trip LVS gate remains unresolved.

The installed KLayout MOM class compares topology, not W/L. The checker now
also reads the actual LVS database and audits matched CMOM W/L within one
5-nm grid step, and multiplicity. `lvs-klayout/cmom_dimensions.json` records
the measurements. Model-view Netgen additionally compares explicit metal
stack parameters; its W/L tolerance is 10 ppm for native metadata rounding.
The regression below accepts the real filter and rejects changed capacitor
width and stack references; it also exposed and closed the previous
topology-only width-check gap:

```sh
python3 -m unittest discover -s macros/pll_analog/layout -p test_lvs.py -v
```

Magic full-RC still rejects the unexposed rhigh body-coupling endpoint; its
failure gate is unchanged. A separate pinned KPEX 0.6.10 native-RC experiment
is in `build/cic-native-rc-closure-084`, using a geometry-identical flattened
extraction copy with child text removed. It is not an accepted replacement
until its device/port/parameter and electrical checks complete. Well and
substrate resistance are not covered by that backend. See the CIC README
for replay details and limitations.

Do not rerun SPICE import or CIC generation over maintained Magic edits.
Generate experiments in new build directories and promote reviewed changes
explicitly. `.mag` remains the editable layout source; GDS is an export.

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

PEX now preserves the **native Magic extresist netlist byte-for-byte**:
no C-only export, capacitor replacement, node-name rewrite or simulator shunts.
The export remains flat, with zero R/C thresholds and resistor tee off.
`pex/capacitance_model.json` records the native-netlist hash, warning count and
limitations; `pex/extraction.feedback` preserves extraction warning locations.
The result is named `pex-resistance-native-c` to distinguish it from historical
`pex-resistance-lumped-c` runs. Export and port checks are not capacitance
accuracy or foundry signoff, and do not waive extraction warnings.

The retired merge failed because original C-only node names need not survive
resistance extraction. Historical `capacitance_endpoint_audit.json` files
describe that merge, not native Magic DRC errors. Do not interpret those old
reports as current native-export results. The earlier capacitance double-count
workaround has not been established as necessary for current Magic 8.3.685.

A native deck can contain capacitance-only floating conductors (for example,
poly in digital filler cells). A DC `.op` cannot determine their voltage.
For a startup transient, `tran ... uic` can bypass that undefined DC solution;
document the assumed initial capacitor charge and reset/supply stimulus.
This is a testbench choice, not automatic proof of lock or RC accuracy.
Do not silently ground these nodes or discard their coupling capacitors.
Global `rshunt` is not enabled: diagnostic shunts changed the DC solution.
The installed resistor-tee issues described in `../cic/README.md` remain
separate; this change does not split or replace the foundry resistor model.

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
