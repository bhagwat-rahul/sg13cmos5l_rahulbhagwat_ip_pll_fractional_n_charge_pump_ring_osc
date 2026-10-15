# PLL digital + fixed /2 prescaler — integration freeze v1

Use this directory's views for analog layout and top integration. The cell is
`pll_digital`, 160 × 140 µm, in **ihp-sg13cmos5l**, not SG13G2. This is a frozen
integration baseline, **not unconditional full-chip/tapeout sign-off**.
Do not overwrite v1 with a new implementation; create a new version and
requalify the analog interface if the macro changes.

## Views

| Path | Purpose |
| --- | --- |
| `gds/pll_digital.gds` | Actual hierarchical layout, including standard-cell geometry; import/instantiate in Magic and merge into the final chip GDS |
| `lef/pll_digital.lef` | Macro boundary, pins and routing obstructions for top-level P&R |
| `vh/pll_digital.vh` | Empty Verilog declaration for hard-macro instantiation; define `USE_POWER_PINS` for explicit VDD/VSS |
| `pnl/pll_digital.pnl.v` | Routed structural netlist with power connections |
| `nl/pll_digital.nl.v` | Routed functional netlist without explicit power ports |
| `lib/<corner>/*.lib` | LibreLane-generated timing abstracts for this constraint context; not an independently characterized all-mode model |
| `sdf/<corner>/*.sdf`, `spef/nom/*.spef` | Timing/parasitic views for subsequent verification |
| `spice/pll_digital.spice` | Magic-extracted hierarchical LVS view; includes abstract standard-cell entries, not a complete transistor-level simulation deck |
| `sdc/pll_digital.sdc` | Leaf-run constraint reference; do not blindly source internal pin constraints into a top-level black-box design |
| `reports/` | Final metrics, corner timing/clock checks, receiver results and routed functional-test output |

`SHA256SUMS` locks the package contents. Check it from this directory with
`shasum -a 256 -c SHA256SUMS`. `SOURCES.sha256` locks the design/flow/test inputs;
check it from the repository root with
`shasum -a 256 -c macros/pll_digital/frozen/v1/SOURCES.sha256`.
`manifest.json` records provenance and scope; generated run directories are
ignored, but this package is intended to be committed and pushed.

## Interface contract

All signals use the digital VDD/VSS domain (nominal 1.20 V). Connect the macro's
Metal4 VDD/VSS pin shapes shown in LEF into the top-level supply network; do not
assume power connectivity from the GDS placement alone. Respect LEF obstructions.

| Port | Connection / meaning |
| --- | --- |
| `VDD`, `VSS` | Digital supply and ground |
| `vco_clk` | Analog ring's buffered VCO output → inv4/inv16 receiver → fixed /2 DFRBP2 |
| `ref_clk` | Reference clock; 100 MHz in the implementation constraints |
| `up`, `down` | Digital PFD outputs → analog charge-pump controls |
| `reset_n` | Active-low asynchronous reset; release protocol still needs mixed-signal qualification |
| `enable` | Low holds the digital state reset; configure while disabled |
| `div_ratio[9:0]` | Q7.3 ratio: integer N in [9:3], fraction in [2:0]; valid N=4…127 |
| `test_div_select[1:0]` | 00: VCO/2; 01: VCO/4; 10: VCO/8; 11: VCO/16 |
| `test_clk` | Divided clock for the chip's output path; at 2 GHz VCO, select 01 or slower to stay below 800 MHz |
| `pll_clk` | Internal VCO/2 clock, also driving the feedback divider; not a second external clock output |
| `feedback_clk` | Internal divider/PFD feedback observation port; do not externally feed it back into the macro |

Hold ratio and output selection stable while enabled. Avoid adding loads to
internal clock observation ports without rechecking timing and receiver loading.
Use an appropriate pad/output driver: this macro was not designed to drive
package capacitance directly. For a nominal 2 GHz / 100 MHz integer lock,
`div_ratio=160` represents N=20, fraction=0.

## Verified checkpoint

Run `digital-freeze-v1` used the default YAML with **no config overrides**:
DELAY 0, protected inv4 → inv16 input receiver, complementary DFRBP2 /2,
2 GHz VCO / 1 GHz half-rate and 25 ps uncertainty. The routed netlist and LEF
are byte-identical to the tested `receiver-inv4-delay0` candidate.

| Extracted STA metric (ps) | TT | FF | SS |
| --- | ---: | ---: | ---: |
| Setup slack | +184.496 | +291.726 | +13.616 |
| Hold slack | +167.326 | +106.804 | +273.020 |
| Minimum clock pulse-width slack | +103.106 | +162.672 | +7.949 |

All-corner TNS is zero. Magic/KLayout DRC, LVS, antenna, max fanout, capacitance
and slew checks report zero violations. There are 600 functional standard cells
(115 sequential cells), plus 703 fill-class cells; functional area is
11004.3 µm², core area 16258.8 µm² and utilization 67.6822%.

Fresh routed-netlist zero-delay tests passed all 992 ratio combinations,
four output selections and reset/disable controls. This is **not SDF simulation**.
Fresh transistor-level receiver probes using this run's nominal routed RC and
the current schematic ring passed TT/FF/SS division/swing checks. SS at
1.08 V / 125 C gives 2.00023 GHz input → 1.00011 GHz Q output, with Q peak
0.920 V. The old buf16 receiver fails the equivalent SS probe (Q peak 0.185 V).

### Remaining chip-level qualification — not waived by this freeze

- The flow explicitly skips `Checker.YosysSynthChecks` for the **two intentional
  asynchronous PFD reset loops**. Other checkers remain enabled. PFD dead zone,
  reset pulse width and asynchronous release/recovery still need validation.
- STA uses 50% VCO input duty, 150 ps input transition, 5 fF output loads,
  enabled mode and output selection 01. Ratio logic is not case-specialized,
  but feedback/PFD clocks are an independent 100 MHz integer-mode model.
  Other output modes, fractional PFD edge spacing and top-level clock endpoint
  budgets are not fully sign-off qualified by these STA numbers.
- `check_setup` reports no unclocked registers, but reports 11 inputs without
  input delays (static `div_ratio[9:0]` and asynchronous `reset_n`) and three
  unconstrained output endpoints (`pll_clk`, `test_clk`, `feedback_clk`).
  Their external timing budgets must be defined at integration; internal
  register-to-register timing is checked. See `reports/*/clock-coverage.txt`.
- Receiver probes sample one VCTRL per PVT corner near 2 GHz (TT about 2.10 GHz,
  FF about 2.02 GHz, SS about 2.00 GHz), over a 20–30 ns measurement window.
  They use schematic analog devices, nominal wire RC, quiet unmodeled coupling
  neighbors, two clock-root input loads and dummy root-output loads. They do
  not establish maximum acquisition frequency, jitter, mismatch, all duty/slew
  combinations, supply-noise robustness or extracted analog behavior.
- Recheck actual analog routing/loading, charge-pump input capacitance and
  output pad load in the integrated design. UP/DOWN's 200 ps interface budget
  is provisional. Small SS timing/pulse margins make this important.
- Top-level DRC/LVS/antenna, supply integrity, SDF/reset checks and extracted
  closed-loop mixed-signal validation remain required before tapeout.

## Reproduce

From the repository root inside IIC-OSIC-TOOLS 2026.08 (LibreLane 3.1.0.dev3):

```sh
source .designinit
librelane macros/pll_digital/flow/librelane/config.yaml \
  --pdk "$PDK" --pdk-root "$PDK_ROOT" --manual-pdk \
  --run-tag digital-freeze-v1-reproduce \
  --skip Checker.YosysSynthChecks --jobs 4 --condensed

python3 macros/pll_digital/flow/librelane/qualify_receiver.py \
  macros/pll_digital/flow/librelane/runs/digital-freeze-v1-reproduce \
  --output .amp/in/artifacts/digital-freeze-v1-reproduce-receiver

iverilog -g2012 -s tb_routed_pll -o /tmp/pll-routed.vvp \
  macros/pll_digital/testbenches/verilog/tb_routed_pll.v \
  macros/pll_digital/flow/librelane/runs/digital-freeze-v1-reproduce/final/nl/pll_digital.nl.v \
  "$PDK_ROOT/$PDK/libs.ref/sg13cmos5l_stdcell/verilog/sg13cmos5l_stdcell.v" \
  "$PDK_ROOT/$PDK/libs.ref/sg13cmos5l_stdcell/verilog/sg13cmos5l_udp.v"
vvp /tmp/pll-routed.vvp
```

The PDK model's `ifnone` specify-path warnings in Icarus do not prevent the
zero-delay functional test; they are another reason not to claim SDF validation.
Reproduction must pass checks again, not merely produce a GDS. Binary GDS and
some report headers include timestamps; use geometry comparison for reruns,
not only a file hash. The schedule remains cleared; no automatic reruns occur.
