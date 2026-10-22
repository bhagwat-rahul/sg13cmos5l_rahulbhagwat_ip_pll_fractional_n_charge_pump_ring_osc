# Slot13 integration draft — not signoff

`gds/slot_13.gds` is the connected, hierarchical PLL slot for the Chipalooza
integration workflow. The top cell is `slot_13`, with the unchanged harness
access geometry and slot coordinates (0, 0) to (537.15, 273) µm. It contains
the unfilled compact PLL, not the earlier placement-only preview. External
pads remain part of the harness; no pad/config/interface changes are bundled.

The `final/` directory is the harness's discovery location, **not a claim of
electrical freeze, foundry acceptance or completed submission**. The older
`sg13cmos5l_chipalooza_analog_project.*` files are legacy template views, not
the PLL release. The slot finder selects the exact `slot_13.gds` filename.
No new LEF, Liberty or HDL timing model is supplied by this draft.

## Contents and provenance

- `gds/slot_13.gds`: byte-for-byte copy of the annotated, LVS-checked stream
  from `layout/core/checks/slot_13/20261022-053728-293987/slot_13.gds`.
  SHA256: `2d74596c04dfcec6c5879b8bada21d858b4dec54a3799dd4b89107b330442d2e`.
- `netlist/slot_13.spice` and `.cdl`: complete source-derived LVS references
  from that run, including the analog circuits, powered frozen digital and
  PDK standard-cell definitions. These are **not RC simulation decks**.
  Reconcile shared library definitions when loading into top-level LVS;
  simply adding the GDS does not install this circuit into the top reference.
- `reports/slot_13-maintained-lvs.json`: passing checks of maintained sources.
- `reports/slot_13-digital-geometry.json`: unchanged frozen-digital polygons
  and the SHA256 of this exact stream.
- `reports/slot_13-full-checks.json`: full candidate039 check, whose stream
  has empty polygon XOR against the packaged stream on all 33 layer/purpose
  pairs. Original local report paths are retained for traceability.

Editable layout is `layout/core/mag/slot_13.mag`; the source connection
contract is `schematic/slot_13.spice`. Connection mapping, regeneration and
check commands are in `layout/core/README.md`. Reset is active-low;
`ibias0` must deliver +2 µA into IREF. Clock terminal 0 is reference input
and terminal 1 is clock output. Separate `_esd` access terminals are unused.

## Current checks and open gates

Magic DRC, source/model-view Netgen LVS, independent GDS/KLayout LVS with
CMOM dimension checks, Magic/KLayout antenna and frozen-digital preservation
pass. The complete checker nevertheless returns **FAIL**:

- Full KLayout reports seven unfilled-slot global density violations:
  AFil.g, GFil.g, M1.j, M2.j, M3.j, M4.j, TM1.c. No other KLayout markers
  remain. Chip-level fill and subsequent checks are still required.
- Magic PEX rejects 2,836 C-only endpoints missing from its resistance
  network. Accepted full RC and post-route/post-fill electrical qualification
  remain open; successful LVS is not parasitic or performance signoff.
- Full-chip connection/LVS, pad loading and voltage compatibility, PDN IR/EM,
  ESD, PVT/lock/timing and final density closure are not established here.

## Harness integration

After publishing this revision in the project repository, from the sibling
`sg13cmos5l_ocd_chipalooza` checkout inside the tools container:

```sh
export PDK_ROOT=/foss/pdks
export PDK=ihp-sg13cmos5l
make projects SLOTS=13
make projects-gds SLOTS=13
make gds-prefill
make drc
```

The harness must select the revision containing this file. Its current
`s13_source` already names this repository. If slot13 is already checked out
at an older pinned revision, update its version selection and use
`make projects-update SLOTS=13` before rediscovering GDS. The project scripts
may stage submodule/version changes; inspect them before committing.

`SLOTS=13` limits the generated placement list to slot13, appropriate for
this draft test. For a complete multi-project chip regenerate the list for
all intended slots. Inspect assembly output for missing cells and placement
warnings; a written chip GDS alone does not prove successful integration.

Next integrate the PLL circuit into the top LVS reference and run extraction
and LVS. Then follow the harness's fill/final-stream/DRC/LVS flow. No top-level
assembly, push, PR or foundry submission has been performed by packaging this
draft.
