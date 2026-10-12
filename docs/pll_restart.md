# PLL source migration and manual-layout restart

## Baseline and boundaries

Imported on 2026-10-12 from the clean local checkout of
[Intubun/chipalooza_lvds_pll at the migration baseline](https://github.com/Intubun/chipalooza_lvds_pll/commit/5b8222a0ff7c549aa832e697d6eb46af14df723e).
The 64 imported files retain their original paths, contents, and executable
permissions. The source repository and MPW wrapper were not modified.

| Directory | Retained sources |
| --- | --- |
| `macros/pll_analog/schematic/xschem/` | Analog hierarchy, simulation PFD/dividers, symbols and Xschem configuration |
| `macros/pll_analog/testbenches/xschem/` | Block and closed-loop benches, including RTL/transistor co-simulation |
| `macros/pll_analog/cace/` | VCO characterization specification, schematic template and generator |
| `macros/pll_digital/rtl/` | PFD, fractional feedback divider, output divider, digital top and behavioral loop model |
| `macros/pll_digital/testbenches/verilog/` | Four existing RTL benches |
| `macros/pll_digital/schematic/xschem/` | Digital macro symbol and library configuration |
| `macros/pll_digital/scripts/` | Symbol generation, SPICE-to-XSPICE conversion and PEX port checking |
| `macros/pll_prescaler/models/` | Prescaler Verilog model, not its physical implementation |
| `scripts/pll/` | Simulation, bridge/port support and characterization scripts |

Not imported: LVDS circuitry, the old `slot_14` top and benches, any PLL
GDS/LEF/Magic layout, generated device cells, extracted/gate-level netlists,
reports, old physical-flow configuration, or automatic layout generators.
This is deliberately not a tapeout-ready macro. Existing inverter/counter
files in this repository belong to the original template and remain only as
flow references. Explicit PLL submission paths prevent their deliverables
from being mistaken for this PLL.

## Which schematic to use

- `pll_analog.sch` is the transistor-level analog core: charge pump, loop
  filter and buffered ring oscillator (with inverter and VCO-bias hierarchy).
- `pll_cosim.sch` combines that core with the configurable `pll_digital` RTL
  through an ngspice `d_cosim` boundary. Use it to establish the pre-layout
  baseline; that boundary is a simulation model, not a physical cell.
- `pll.sch` uses XSPICE digital PFD/divider models. It is a useful integer-N
  simulation reference, not the standalone manufacturable top.
- `pll_digital.sym` describes the eventual digital macro interface; its
  generated implementation netlist is intentionally absent.

The digital ratio is Q7.3. The ring runs at twice the main PLL output rate;
feedback shares the output's full-rate divide-by-two stage. The RTL models
that stage as a toggle flip-flop. The old physical implementation substituted
a custom TSPC prescaler; neither its layout nor synthesis mapping was imported.
Its redesign, characterization, timing model and new mapping must precede
digital hardening. Behavioral RTL success does not validate that physical
full-rate stage.

## Reproduce the schematic baseline

From this repository root:

```sh
# Icarus Verilog on PATH, or set IVERILOG and VVP explicitly.
make pll-test

# Run the following inside IIC-OSIC-TOOLS 2026.08 or later.
make pll-cosim
CORNERS=tt VDDS=1.20 TEMPS=27 VCTRLS=0.80 make pll-ring
CORNERS=tt VDDS=1.20 TEMPS=27 VCTRLS=0.70 make pll-charge-pump

# Full PVT characterization (longer runs).
make pll-ring
make pll-charge-pump
make pll-cace

# Open the configurable simulation hierarchy with its local library setup.
(cd macros/pll_analog/schematic/xschem && xschem pll_cosim.sch)
```

`pll-test` checks the fractional divider and nine behavioral closed-loop
operating points. The additional benches `tb_pfd.v` and
`tb_clock_output_divider.v` can be compiled independently with their RTL.
The analog scripts use the container's `/foss` tools and IHP PDK; they are not
portable host-only analog simulation commands. `pll-cosim` accepts `DIV_RATIO`,
`TEST_DIV`, `FREF_HZ`, `VDD`, `CORNER`, `TEMP_C`, and `SIM_TIME_S` overrides.
Its default is ratio 160 (20.0), 100 MHz reference and a 1 GHz main output.

### Migration checks run on 2026-10-12

- All 64 imports matched source bytes and file permissions.
- All 12 analog schematics and eight benches netlisted with Xschem in the
  running IIC-OSIC-TOOLS 2026.08 container, without missing-symbol errors.
- `make pll-test` passed: 992 fractional-divider cases (integer fields 4–127,
  all eight fractional fields) and nine behavioral closed-loop cases.
- The separate PFD and output-divider RTL benches passed; PFD lead/lag
  pulses were 2 ns, and output selections divided by 2, 4, 8 and 16.
- Nominal charge-pump characterization at 1.2 V, 27 °C, VCTRL=0.70 V
  measured +2.820853 µA / −2.820430 µA with 0.0150% mismatch.
- Nominal ring characterization at 1.2 V, 27 °C, VCTRL=0.80 V measured
  4.72277321 GHz with 163.885 µA supply current.
- `make pll-cosim` passed at tt, 1.2 V, 27 °C, 100 MHz reference and ratio
  20.0: main output 1.000000 GHz, average VCTRL 0.543149 V. It produced
  101 settled output edges and met the runner's 1% frequency-error check.

These checks establish that the migrated simulation sources run without the
old physical implementation. They are not full PVT characterization, physical
prescaler verification, loop-stability proof, or post-layout sign-off. CACE
and the full analog PVT sweeps have not been run as part of this migration.

## Standalone MPW integration is not yet assigned

The sibling `sg13cmos5l_ocd_chipalooza/config.txt` still assigns slot 14 to
LVDS and slot 6 to a different PLL; slot 13 has a placeholder URL. That does
**not** establish slot 13 as our allocation. Confirm the actual slot and
dimensions before choosing a floorplan or placing circuitry.

The inspected `verilog/rtl/slot13_wrapper.v` offers a 24-bit digital input
bus, 12-bit output bus, enable/clock/reset, gated 1.2 V and 3.3 V supplies,
two dedicated analog pads plus secondary ESD pins, shared current/voltage
biases and four analog buses. Other slots can differ. Its simulation supply
and bias ports are `real`, while dedicated pads are wires; this behavioral
contract is not itself the physical macro header.

Before drawing a top or routing pins, settle:

1. Assigned slot, usable dimensions, pad allocation, macro/cell naming and
   physical header conventions with the wrapper owner.
2. Reference-clock path and expected frequency range; which outputs must
   reach dedicated pads rather than the shared digital bus.
3. Bit assignment for the 10-bit ratio, two-bit test divider, and diagnostics;
   wrapper reset polarity versus PLL `reset_n`; disabled/power-gated behavior.
4. Core supply/ground mapping, bias-current magnitude and direction (the
   existing charge-pump benches inject 2 µA into IREF), output loads,
   buffering, level shifting and ESD ownership. Do not assume shared bias
   compatibility solely from the port names.

`submission.yaml` uses the intended unique top name, but slot size and analog
pin count are intentionally unset. Fill them in only after this interface is
agreed. Root physical targets will need the new matching schematic and layout;
`make all` is not meaningful yet. The old template can still be explored with
an explicit `TOP=sg13cmos5l_chipalooza_analog_project`, but its checks are not PLL
verification.

## Manual physical-design sequence

1. **Freeze a schematic baseline.** Review device sizing, charge-pump
   compliance/mismatch, loop stability, VCO tuning/startup and output swing
   across PVT. Exercise ratio boundaries, reset/enable and integer/fractional
   lock cases. Record loads and acceptance limits before layout.
2. **Plan the mixed-signal floorplan.** Select the confirmed slot outline;
   budget the loop-filter passives, analog core, full-rate prescaler and
   standard-cell digital block. Plan supplies, wells/taps, guard rings,
   clock paths and analog/digital isolation before placing devices.
3. **Lay out analog cells manually, bottom-up.** Start with inverter,
   VCO bias and buffer; assemble the ring, charge pump and loop filter, then
   `pll_analog`. Preserve matching and symmetry where required, provide
   legal pin access, keep VCTRL short/quiet, and control clock coupling.
   Run DRC and LVS on each cell before building its parent.
4. **Extract and characterize each critical cell.** Check full-RC PEX
   against the schematic baseline, especially VCO tuning/startup, charge-pump
   matching and the redesigned full-rate prescaler. Revisit sizing/layout
   before freezing macro views.
5. **Rebuild digital physical design.** Create fresh SDC, floorplan, pin
   placement and PDN configuration against the new prescaler views/mapping;
   synthesize and place/route `pll_digital`. Verify timing, DRC/LVS, antenna,
   reset and divider behavior. Do not reuse the old hard-coded placement.
6. **Build the standalone mixed-signal top.** Draw its actual MPW interface
   and assemble the new analog/digital cells. Check hierarchy, supplies,
   enable/reset, bias wiring and pad paths against the agreed pin map.
7. **Close top-level sign-off.** Repeat DRC/LVS/antenna and full-RC extraction;
   run extracted mixed-signal simulations across the agreed PVT/ratio/load
   matrix. Export matching GDS, LEF and header, then validate integration with
   the assigned MPW wrapper. Prior repository results are not sign-off for
   this implementation.

This migration establishes the source starting point only. It does not choose
a new circuit architecture or begin automatic layout.
