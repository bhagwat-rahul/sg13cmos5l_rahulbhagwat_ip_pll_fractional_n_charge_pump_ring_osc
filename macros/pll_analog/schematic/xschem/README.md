# Analog PLL schematic wiring reference

Use these tables to replace label-only connections with visible Xschem wires
without changing the circuit. This is the connectivity baseline from the
seven ordinary schematic SPICE files in [`../../netlist/schematic/`](../../netlist/schematic/),
checked on 2026-10-12. It is not a schematic redesign or layout instruction.
Regenerate and compare the netlists after redrawing; these tables are a
snapshot, not an automatically updated source of truth.

## What the seven cells cover

The seven `.sch` files below are the complete local hierarchy of
[`pll_analog.sch`](pll_analog.sch): charge pump, loop filter and buffered VCO.
Keep their corresponding `.sym` files and `xschemrc` as well. The seven SPICE
files alone are not editable Xschem schematics.

They are **not the entire PLL**. The implementation PFD, fractional feedback
divider and output divider are RTL in `../../../pll_digital/rtl/`.
[`pll_cosim.sch`](pll_cosim.sch) connects that digital model to the analog
core for simulation. `pll.sch`, `pfd.sch`, `feedback_divider.sch`, and
`output_divider.sch` also exist as simulation-model schematics; they are not
additional transistor cells inside `pll_analog`. The standalone MPW top is
still separate work.

## Reading and using the tables

- A table entry names an **electrical terminal**, not its screen position.
  Rotation/mirroring changes where a pin is drawn, not which terminal it is.
- MOS terminals are `D` (drain), `G` (gate), `S` (source), `B` (bulk/body).
  The PDK SPICE order is **D, G, S, B**, for both NMOS and PMOS. Do not
  exchange D/S or leave the body disconnected just to make drawing easier.
- The tables use Xschem instance names: e.g. `M1` is netlisted as `XM1`
  because these PDK devices use `spiceprefix=X`. Likewise `R1` → `XR1`
  and `C1A` → `XC1A`. The extra `X` is not a different device.
- Equal net names **within one cell** must connect electrically. Names such
  as `net1`/`net2` are local: `inverter.net1` is not `vco_buffer.net1`, nor
  the `net1` between the ring's inverter instances.
- Keep existing net labels on the new wires, especially `VCTRL`, `VCO_CORE`,
  `VBP`, `net1`, and `net2`: benches use hierarchical node names for probes
  and oscillator initial conditions. Do not introduce `0` in place of the
  reusable cells' `VSS` port; their testbenches make the ground connection.
- Pins with the same label are already electrically joined in Xschem even
  without a drawn wire. This cleanup should change readability, not topology.
  Draw onto actual symbol pins, verify junctions, and avoid accidental shorts
  at wire crossings. Retain device parameters and simulator/model blocks.

## 1. `pll_analog.sch` — analog top

External SPICE port order: `UP DOWN IREF VCO_CLK VDD VSS`.
`VCTRL` is an internal net, not an external port of this cell.

| Xschem instance | Child cell | Child port | Connect to net |
| --- | --- | --- | --- |
| x_charge_pump | charge_pump | UP | UP |
| x_charge_pump | charge_pump | DOWN | DOWN |
| x_charge_pump | charge_pump | IREF | IREF |
| x_charge_pump | charge_pump | VCTRL | VCTRL |
| x_charge_pump | charge_pump | VDD | VDD |
| x_charge_pump | charge_pump | VSS | VSS |
| x_loop_filter | loop_filter | VCTRL | VCTRL |
| x_loop_filter | loop_filter | VSS | VSS |
| x_vco | ring_oscillator | VCTRL | VCTRL |
| x_vco | ring_oscillator | VCO_OUT | VCO_CLK |
| x_vco | ring_oscillator | VDD | VDD |
| x_vco | ring_oscillator | VSS | VSS |

Draw a visible `VCTRL` connection from `x_charge_pump.VCTRL` to both
`x_loop_filter.VCTRL` and `x_vco.VCTRL`. Connect `x_vco.VCO_OUT` to the
top-level `VCO_CLK` output pin. All three child cells share `VSS`; the charge
pump and ring also share `VDD`.

## 2. `charge_pump.sch` — nine MOS devices

External SPICE port order: `UP DOWN IREF VCTRL VDD VSS`.

| Xschem instance | PDK device | D | G | S | B |
| --- | --- | --- | --- | --- | --- |
| M_UP_INV_P | sg13_lv_pmos | UP_B | UP | VDD | VDD |
| M_UP_INV_N | sg13_lv_nmos | UP_B | UP | VSS | VSS |
| M_IREF | sg13_lv_nmos | IREF | IREF | VSS | VSS |
| M_PBIAS | sg13_lv_pmos | PBIAS | PBIAS | VDD | VDD |
| M_PBIAS_SINK | sg13_lv_nmos | PBIAS | IREF | VSS | VSS |
| M_UP_SOURCE | sg13_lv_pmos | P_UP | PBIAS | VDD | VDD |
| M_UP_SWITCH | sg13_lv_pmos | VCTRL | UP_B | P_UP | VDD |
| M_DOWN_SWITCH | sg13_lv_nmos | VCTRL | DOWN | N_DOWN | VSS |
| M_DOWN_SINK | sg13_lv_nmos | N_DOWN | IREF | VSS | VSS |

Useful wire groups when drawing:

- `UP` joins both input-inverter gates; `UP_B` joins their drains and
  `M_UP_SWITCH.G`.
- `IREF` joins its external pin, `M_IREF.D`, `M_IREF.G`,
  `M_PBIAS_SINK.G`, and `M_DOWN_SINK.G`.
- `PBIAS` joins `M_PBIAS.D`, `M_PBIAS.G`, `M_PBIAS_SINK.D`, and
  `M_UP_SOURCE.G`.
- `P_UP` joins `M_UP_SOURCE.D` to `M_UP_SWITCH.S`.
- `N_DOWN` joins `M_DOWN_SWITCH.S` to `M_DOWN_SINK.D`.
- `VCTRL` joins `M_UP_SWITCH.D`, `M_DOWN_SWITCH.D`, and its external pin.
  `DOWN` connects directly to `M_DOWN_SWITCH.G`.
- Every PMOS body goes to `VDD`, even when its source is `P_UP`.
  Every NMOS body goes to `VSS`, even when its source is `N_DOWN`.

## 3. `loop_filter.sch` — resistor and two capacitors

External SPICE port order: `VCTRL VSS`.

| Xschem instance | PDK device | Terminal/property | Connect to net |
| --- | --- | --- | --- |
| R1 | rhigh | P | VCTRL |
| R1 | rhigh | M | FILTER_ZERO |
| R1 | rhigh | body property | VSS |
| C1A | cap_cmomf | c0 | FILTER_ZERO |
| C1A | cap_cmomf | c1 | VSS |
| C2 | cap_cmomf | c0 | VCTRL |
| C2 | cap_cmomf | c1 | VSS |

Draw the series branch `VCTRL → R1.P/R1.M → FILTER_ZERO → C1A.c0/C1A.c1 → VSS`.
`C2` is a separate shunt branch directly between `VCTRL` and `VSS`.
`FILTER_ZERO` is only the R1–C1A junction; **do not short it to VCTRL**.

The resistor symbol has only two visible pins, `P` and `M`. Its third SPICE
node is emitted from the instance's **`body=VSS` property**; retain that
property rather than looking for a nonexistent third symbol pin. The
capacitor symbols use `c0`/`c1`, not MOS-style terminals. Keep schematic
capacitor parameters `mmin=2 mmax=4`; `metal2`/`metal4` strings belong only to
the separate Magic-import netlists.

## 4. `ring_oscillator.sch` — three-stage ring, bias and buffer

External SPICE port order: `VCTRL VCO_OUT VDD VSS`.

| Xschem instance | Child cell | Child port | Connect to net |
| --- | --- | --- | --- |
| x1 | inverter | VIN | VCO_CORE |
| x1 | inverter | VOUT | net1 |
| x1 | inverter | VBP | VBP |
| x1 | inverter | VDD | VDD |
| x1 | inverter | VBN | VCTRL |
| x1 | inverter | VSS | VSS |
| x2 | inverter | VIN | net1 |
| x2 | inverter | VOUT | net2 |
| x2 | inverter | VBP | VBP |
| x2 | inverter | VDD | VDD |
| x2 | inverter | VBN | VCTRL |
| x2 | inverter | VSS | VSS |
| x3 | inverter | VIN | net2 |
| x3 | inverter | VOUT | VCO_CORE |
| x3 | inverter | VBP | VBP |
| x3 | inverter | VDD | VDD |
| x3 | inverter | VBN | VCTRL |
| x3 | inverter | VSS | VSS |
| x_bias | vco_bias | VCTRL | VCTRL |
| x_bias | vco_bias | VBP | VBP |
| x_bias | vco_bias | VDD | VDD |
| x_bias | vco_bias | VSS | VSS |
| x_buffer | vco_buffer | VIN | VCO_CORE |
| x_buffer | vco_buffer | VOUT | VCO_OUT |
| x_buffer | vco_buffer | VDD | VDD |
| x_buffer | vco_buffer | VSS | VSS |

The feedback loop is `x1.VOUT → x2.VIN`, `x2.VOUT → x3.VIN`,
and `x3.VOUT → x1.VIN`. Its last connection is `VCO_CORE`, which also drives
`x_buffer.VIN`. The external `VCO_OUT` comes **after the buffer**, not directly
from the ring node. All inverter `VBN` pins take `VCTRL`; all inverter `VBP`
pins take the bias block's `VBP` output. Do not join `VBP` to `VCTRL`.

## 5. `inverter.sch` — current-starved inverter

External SPICE port order: `VIN VOUT VBP VDD VBN VSS`.
This is not a two-device ordinary CMOS inverter.

| Xschem instance | PDK device | D | G | S | B |
| --- | --- | --- | --- | --- | --- |
| M1 | sg13_lv_pmos | net1 | VBP | VDD | VDD |
| M2 | sg13_lv_pmos | VOUT | VIN | net1 | VDD |
| M3 | sg13_lv_nmos | VOUT | VIN | net2 | VSS |
| M4 | sg13_lv_nmos | net2 | VBN | VSS | VSS |

Connect `M1.D` to `M2.S` (`net1`), and `M3.S` to `M4.D` (`net2`).
Join `M2.D` and `M3.D` to the `VOUT` pin. `VIN` joins the gates of `M2`
and `M3`; `VBP` drives only `M1.G`, and `VBN` drives only `M4.G`.
Keep both PMOS bodies on `VDD` and both NMOS bodies on `VSS`, independently
of the internal source nodes.

## 6. `vco_bias.sch` — PMOS bias generator

External SPICE port order: `VCTRL VBP VDD VSS`.

| Xschem instance | PDK device | D | G | S | B |
| --- | --- | --- | --- | --- | --- |
| M1 | sg13_lv_pmos | VBP | VBP | VDD | VDD |
| M2 | sg13_lv_nmos | VBP | VCTRL | VSS | VSS |

Join `M1.D`, `M1.G`, `M2.D`, and the `VBP` output pin. This makes `M1`
diode-connected. The `VCTRL` input drives `M2.G`; it is not directly wired
to `VBP`.

## 7. `vco_buffer.sch` — two ordinary inverter stages

External SPICE port order: `VIN VOUT VDD VSS`.

| Xschem instance | PDK device | D | G | S | B |
| --- | --- | --- | --- | --- | --- |
| M1 | sg13_lv_pmos | net1 | VIN | VDD | VDD |
| M2 | sg13_lv_nmos | net1 | VIN | VSS | VSS |
| M3 | sg13_lv_pmos | VOUT | net1 | VDD | VDD |
| M4 | sg13_lv_nmos | VOUT | net1 | VSS | VSS |

Join `M1.G` and `M2.G` to `VIN`. Join `M1.D`, `M2.D`, `M3.G`, and
`M4.G` as the interstage `net1`. Join `M3.D` and `M4.D` to `VOUT`.
Both stages share supply rails and body connections. This buffer has no
`VBP`/`VBN` ports; do not copy the current-starved inverter's wiring into it.

## Check after each redraw

1. Preserve symbol and instance names, top-level pin names/order, model
   selection, device sizing/fingers/multiplicity, and local net names.
2. Generate a fresh hierarchical schematic netlist. Compare each instance's
   terminal connections to this baseline; cosmetic coordinates and comments
   may change, but electrical connectivity and parameters should not.
3. Run the relevant block bench, then `make pll-test` and `make pll-cosim`
   before proceeding to layout. Netlist generation alone does not prove that
   the circuit still behaves correctly.

No `.sch`, `.sym`, RTL, or layout file was modified to create this guide.
