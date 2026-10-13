v {xschem version=3.4.8RC file_version=1.3}
G {}
K {}
V {}
S {}
F {}
E {}
T {Custom-layout analog portion of the PLL.
Digital PFD/divider logic drives UP and DOWN and consumes VCO_CLK.} -280 -350 0 0 0.3 0.3 {}
N -480 -90 -410 -90 {lab=UP}
N -480 -70 -410 -70 {lab=DOWN}
N -110 -70 -60 -70 {lab=IREF}
N -110 -50 0 -50 {lab=#net1}
N 300 -50 340 -50 {lab=VDD}
N 340 -90 340 -50 {lab=VDD}
N -110 -90 340 -90 {lab=VDD}
N 0 -50 0 30 {lab=#net1}
N -110 -30 -110 50 {lab=VSS}
N -110 50 0 50 {lab=VSS}
N 0 50 0 90 {lab=VSS}
N 0 90 300 90 {lab=VSS}
N 300 -10 300 90 {lab=VSS}
N 300 -30 360 -30 {lab=VCO_CLK}
C {charge_pump.sym} -260 -60 0 0 {name=x_charge_pump}
C {loop_filter.sym} 150 40 0 1 {name=x_loop_filter}
C {ring_oscillator.sym} 150 -30 0 0 {name=x_vco}
C {ipin.sym} -480 -90 0 0 {name=p_UP lab=UP}
C {ipin.sym} -480 -70 0 0 {name=p_DOWN lab=DOWN}
C {iopin.sym} -60 -70 0 0 {name=p_IREF lab=IREF}
C {opin.sym} 360 -30 0 0 {name=p_VCO_CLK lab=VCO_CLK}
C {iopin.sym} 140 -90 3 0 {name=p_VDD lab=VDD}
C {iopin.sym} 0 90 2 0 {name=p_VSS lab=VSS}
