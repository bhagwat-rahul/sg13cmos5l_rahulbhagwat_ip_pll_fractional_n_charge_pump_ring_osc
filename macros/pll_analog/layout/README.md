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
| PEX | Flattened layout, coupling capacitance, explicit `extresist all`, 0 mΩ extraction threshold, 1 mΩ simplification, no delay filtering, 0 capacitance output threshold; existing port-fragment validation |

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

Each run prints its report directory and writes `summary.txt`, `summary.json`,
input SHA256 hashes, per-tool logs, Magic DRC coordinates, KLayout `.lyrdb`
markers, LVS reports/databases, antenna feedback, and the PEX netlist
`pex/<cell>_pex.spice`. Generated `build/` contents are Git-ignored. Exit status
is nonzero if any requested check fails. Missing reports/tool errors also fail;
an incomplete KLayout run is not accepted as a clean result.

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
