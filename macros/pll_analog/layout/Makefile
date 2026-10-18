SHELL := /bin/bash
.DEFAULT_GOAL := help
CELLS := inverter vco_bias vco_buffer charge_pump loop_filter ring_oscillator pll_analog
MODES := check drc drc-klayout drc-all antenna lvs pex gds-roundtrip
SELECTED := $(filter $(CELLS),$(MAKECMDGOALS))
UNKNOWN := $(filter-out help check-all $(MODES) $(CELLS),$(MAKECMDGOALS))
ifneq ($(UNKNOWN),)
$(error Unknown target/cell: $(UNKNOWN). Cells: $(CELLS))
endif

.PHONY: help check-all $(MODES) $(CELLS)
help:
	@echo 'make check [cell]  Full installed-PDK checks (default: pll_analog)'
	@echo 'make check-all     Check all seven circuit cells, including analog top'
	@echo 'make {drc|drc-klayout|drc-all|antenna|lvs|pex|gds-roundtrip} [cell]'
	@echo 'Run inside IIC-OSIC-TOOLS; save the Magic/Xschem edits first.'

$(MODES):
	python3 run_checks.py $(if $(filter check,$@),all,$@) $(if $(SELECTED),$(SELECTED),pll_analog)

check-all:
	python3 run_checks.py all $(CELLS)

# The second word in `make check charge_pump` selects a cell, not a file target.
$(CELLS):
	@:
