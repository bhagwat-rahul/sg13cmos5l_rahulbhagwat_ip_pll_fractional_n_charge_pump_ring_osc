# Analog PLL netlists for Magic device import

Generated from the PLL-only repository's Xschem schematics on 2026-10-12.
These are **layout-import inputs**, not simulation decks or LVS references.
No old layout was used, and no generated layout is delivered here.

Files: `inverter.spice`, `vco_bias.spice`, `vco_buffer.spice`,
`charge_pump.spice`, `loop_filter.spice`, `ring_oscillator.spice`,
and `pll_analog.spice`.

Each file includes its schematic hierarchy. They were exported with the root
Makefile's `magic-lvs-netlist` target, using `top_is_subckt=1`, after sourcing
`.designinit` to select **ihp-sg13cmos5l**, not the container's default SG13G2.
For import only, capacitor metal parameters were translated from
`mmin=2 mmax=4` to `mmin=metal2 mmax=metal4`, `mm_ok` was removed, and simulator
`.lib`/`.include` directives were removed. Geometry and circuit connectivity
were otherwise retained. Regenerate ordinary schematic SPICE separately for
LVS; do not substitute these Magic-specific metal strings into simulation.

## Import for manual layout

Start Magic with the SG13CMOS5L startup file in a **new layout directory**.
Keep it separate from the template inverter layout to avoid cell-name clashes.
Inside the IIC-OSIC-TOOLS container, from the PLL repository root:

```sh
source .designinit
mkdir -p macros/pll_analog/layout/mag
cd macros/pll_analog/layout/mag
magic -rcfile "$PDK_ROOT/$PDK/libs.tech/magic/ihp-sg13cmos5l.magicrc"
```

Use **File → Import SPICE**, importing in this bottom-up order:

1. `inverter.spice`
2. `vco_bias.spice`
3. `vco_buffer.spice`
4. `charge_pump.spice`
5. `loop_filter.spice`
6. `ring_oscillator.spice`
7. `pll_analog.spice`

From `layout/mag/`, their relative directory is `../../netlist/magic-import/`.
The console equivalent for each file is:

```tcl
magic::netlist_to_layout ../../netlist/magic-import/inverter.spice sg13cmos5l
```

After all imports, load `pll_analog` and save all generated cells, including
device gencells. Preserve the `.spice` filenames: matching the filename stem
to its top subcircuit ensures that Magic selects that circuit for generation.
Import bottom-up rather than relying on missing hierarchy cells to generate
automatically. Do not repeat the import over cells you have already edited;
this is an initialization operation, not a layout update/merge tool.

The importer supplies device geometry and hierarchy with placeholder ports.
**There is no inter-device routing.** Place devices, match/arrange structures,
connect terminals, implement well/substrate contacts and supplies, and move
ports before performing DRC/LVS/PEX.

## Verification performed

A scratch import with Magic 8.3.681 and the installed SG13CMOS5L gencells
produced all seven circuit cells with the expected direct instance counts:
inverter 4, VCO bias 2, VCO buffer 4, charge pump 9, loop filter 3,
ring oscillator 5, analog top 3. Saved child cells contained geometry, and both
capacitor gencells retained the metal2–metal4 stack. Magic emitted save-time
timestamp/unnamed-cell warnings; no claim of warning-free import or physical
sign-off is made. The scratch layouts were discarded, leaving manual layout
to start from these netlists.
