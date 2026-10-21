# Editable PLL core checkpoint — not a tapeout freeze

`mag/pll_core.mag` is the **unfilled** analog + digital assembly promoted
from CIC candidate008. It includes top wiring and the frozen digital macro's
fixed /2 prescaler. It is not the MPW pad wrapper or an electrically qualified
final design. Do not replace the legacy wrapper GDS with this cell.

## Sources and ownership

- Edit assembly routing in `mag/pll_core.mag`; its reproducible starting recipe
  is `scripts/pll/integrate.py` and its interface is `schematic/pll_core.spice`.
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

An unfilled checkpoint is not expected to close full-chip density. The filled
candidate009 and its physical reports remain separate experiments described in
`../README.md`. Magic's distributed-R/lumped-C endpoint problem is not waived;
the alternative native KPEX RC export has its own required audits. A passing
CC export does not constitute full-RC closure.

## Freeze still requires

Accepted full RC of the final filled geometry; hardware-faithful integrated
transient/PVT, acquisition/overspeed and timing qualification; agreed phase,
ripple and spur budgets; supply/return-path and IR/EM review; pad/ESD/wrapper
integration; and fresh full-chip DRC, LVS, antenna, density and post-fill
electrical checks. No final stream, commit, push or MPW submission is implied.
