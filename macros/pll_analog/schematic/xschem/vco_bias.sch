v {xschem version=3.4.8RC file_version=1.3}
G {}
K {}
V {}
S {}
F {}
E {}
T {Replica bias generator for the current-starved VCO.
VCTRL directly controls the NMOS starvers; the replica branch generates VBP.} -260 -260 0 0 0.3 0.3 {}
N -140 60 -40 60 {lab=VCTRL}
N 0 0 0 30 {lab=VBP}
N -60 -60 -40 -60 {lab=VBP}
N -60 -60 -60 0 {lab=VBP}
N -60 0 0 0 {lab=VBP}
N 0 0 100 0 {lab=VBP}
N 0 -120 0 -60 {lab=VDD}
N 0 -30 0 0 {lab=VBP}
N -0 60 0 120 {lab=VSS}
C {sg13cmos5l_pr/sg13_lv_pmos.sym} -20 -60 0 0 {name=M1
l=0.13u
w=0.15u
ng=1
m=1
mm_ok=1
model=sg13_lv_pmos
spiceprefix=X
}
C {sg13cmos5l_pr/sg13_lv_nmos.sym} -20 60 0 0 {name=M2
l=0.13u
w=0.15u
ng=1
m=1
mm_ok=1
model=sg13_lv_nmos
spiceprefix=X
}
C {ipin.sym} -140 60 0 0 {name=p_VCTRL lab=VCTRL}
C {opin.sym} 100 0 0 0 {name=p_VBP lab=VBP}
C {iopin.sym} 0 -120 3 0 {name=p_VDD lab=VDD}
C {iopin.sym} 0 120 1 0 {name=p_VSS lab=VSS}
