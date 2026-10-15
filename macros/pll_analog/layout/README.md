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
