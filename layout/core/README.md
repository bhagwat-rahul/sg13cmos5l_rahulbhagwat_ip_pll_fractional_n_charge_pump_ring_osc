# Editable PLL core checkpoint — not a tapeout freeze

`mag/pll_core.mag` is the **unfilled** analog + digital assembly promoted
from compact CIC candidate024. It includes top wiring and the frozen digital macro's
fixed /2 prescaler. It is not the MPW pad wrapper or an electrically qualified
final design. Do not replace the legacy wrapper GDS with this cell.

## Sources and ownership

- Edit assembly routing in `mag/pll_core.mag`; its reproducible starting recipe
  is `scripts/pll/fit_slot13.py` and its interface is `schematic/pll_core.spice`.
- The 27 analog `.mag` entries are **relative symlinks** to the maintained
  `macros/pll_analog/layout/mag` library, not independent copies. Editing through
  these links edits the maintained analog sources and invalidates old results.
- Digital cells are readonly imported views of frozen digital v1. Preserve all
  `GDS_FILE`, `GDS_START` and `GDS_END` properties. `mag/pll_digital.gds` is a
  relative symlink to the frozen backing GDS; do not delete it, flatten/repaint
  the digital macro, or treat its interpreted Magic paint as a replacement.
- `manifest.json` records input, backing-stream and packaged-library hashes.
  These describe the checkpoint, not a claim that later manual edits pass.
- No **core-level** density-fill child is included. The frozen digital macro
  retains its own internal fill/tap cells. Generate analog/core density fill
  separately and re-extract after fill or routing changes.

## Open, regenerate and check

Inside IIC-OSIC-TOOLS, from the repository root:

```sh
# Open from the library directory so local cells/backing GDS resolve.
(cd layout/core/mag && magic \
  -rcfile /foss/pdks/ihp-sg13cmos5l/libs.tech/magic/ihp-sg13cmos5l.magicrc \
  pll_core.mag)

# Check maintained files directly, without regenerating or overwriting them.
make pll-core-check CANDIDATE=layout/core MODE=lvs
make pll-core-check CANDIDATE=layout/core MODE=drc
make pll-core-check CANDIDATE=layout/core MODE=antenna

# Rebuild the CIC starting point into a NEW disposable candidate for comparison.
make pll-core CANDIDATE=layout/build/pll-core-regenerate-next
```

Checks snapshot the library and backing stream before operating; reports and
the annotated, geometry-audited stream are under ignored
`checks/pll_core/TIMESTAMP/`. Use that checked stream, not a raw GUI streamout
that omits the CMOM recognition annotations. Do not edit checker snapshots.
The checker intentionally rejects stale generation-input hashes: regenerate
and review provenance after changing the recipe, analog sources or interface.

An unfilled checkpoint is not expected to close full-chip density. Compact filled
candidate031 and its physical reports remain separate experiments described in
`../README.md`. Magic's distributed-R/lumped-C endpoint problem is not waived;
the alternative native KPEX RC export has its own required audits. A passing
CC export does not constitute full-RC closure.

## Promotion validation

The maintained top is byte-identical to unfilled024, with the same analog
links and frozen digital backing stream. Its envelope is 483.2 × 210 µm,
69.197% of slot13. Separate filled031 reaches the larger filled009 checkpoint's
physical-check level: zero-marker full installed KLayout DRC including density
and antenna, Magic DRC/antenna, source Netgen LVS, independent GDS KLayout LVS
with CMOM dimensions, frozen-digital preservation and round-trip geometry
checks all pass. Report:
`../build/pll-slot13-024/checks/pll_core/20261021-135108-071462/`.
Independent all-layer macro/routing preservation and fill-clearance evidence:
`.amp/in/artifacts/pll-slot13-fill-031-audit.json` at the repository root.

Fresh checks of the packaged maintained library also pass Netgen/KLayout LVS,
Magic DRC and Magic/KLayout antenna. Reports under `checks/pll_core/` are
`20261021-143021-246540`, `20261021-143030-127207` and
`20261021-143233-968203`. Its exported GDS matches unfilled024 with empty XOR
on all 31 layer/purpose pairs; evidence is
`.amp/in/artifacts/pll-core-compact031-package-xor.json`. Regeneration through
`make pll-core` reproduces the maintained top byte-for-byte; conservative fill
without the new routing-manifest option reproduces the earlier fill022 child.

The complete checker still returns FAIL on required Magic PEX: 2,797 original
capacitance endpoints are absent from its R export. Native-Magic GDS-reimport
LVS also records the known diagnostic two-CMOM recognition failure; independent
KLayout LVS passes. Neither limitation is hidden or promoted to electrical
signoff. See `../README.md` for the fill recipe and remaining requirements.

## Freeze still requires

Accepted full RC of the final filled geometry; hardware-faithful integrated
transient/PVT, acquisition/overspeed and timing qualification; agreed phase,
ripple and spur budgets; supply/return-path and IR/EM review; pad/ESD/wrapper
integration; and fresh full-chip DRC, LVS, antenna, density and post-fill
electrical checks. No final stream, commit, push or MPW submission is implied.
