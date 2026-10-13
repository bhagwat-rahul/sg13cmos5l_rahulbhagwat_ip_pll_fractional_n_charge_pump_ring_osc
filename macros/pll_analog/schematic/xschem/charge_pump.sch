v {xschem version=3.4.8RC file_version=1.3}
G {}
K {}
V {}
S {}
F {}
E {}
T {Approximately 2.84 uA charge pump with mirrored NMOS/PMOS currents.
IREF is a 2 uA current-input bias node. UP and DOWN are active high.} -280 -390 0 0 0.3 0.3 {}
N 130 -50 170 -50 {lab=IREF}
N 170 -20 170 10 {lab=VSS}
N 170 -210 170 -190 {lab=PBIAS}
N 170 -190 210 -190 {lab=PBIAS}
N 210 -250 210 -220 {lab=VDD}
N 170 -120 170 -90 {lab=VSS}
N 170 40 170 70 {lab=VSS}
N 130 -120 130 -50 {lab=IREF}
N -220 120 -220 160 {lab=UP}
N -190 110 -190 200 {lab=UP_B}
N 170 -20 290 -20 {lab=VSS}
N 170 -190 170 -150 {lab=PBIAS}
N -110 -210 170 -210 {lab=PBIAS}
N 170 -220 170 -210 {lab=PBIAS}
N -110 -210 -110 -140 {lab=PBIAS}
N -150 -250 210 -250 {lab=VDD}
N -150 -250 -150 -140 {lab=VDD}
N -250 -60 -250 40 {lab=VDD}
N -250 -250 -150 -250 {lab=VDD}
N 170 -90 290 -90 {lab=VSS}
N 290 -90 290 -20 {lab=VSS}
N -250 40 -220 40 {lab=VDD}
N -250 200 -220 200 {lab=VSS}
N -250 200 -250 290 {lab=VSS}
N 170 40 290 40 {lab=VSS}
N 290 40 290 290 {lab=VSS}
N 40 290 290 290 {lab=VSS}
N -300 120 -220 120 {lab=UP}
N -220 80 -220 120 {lab=UP}
N 40 70 40 290 {lab=VSS}
N -250 290 40 290 {lab=VSS}
N 40 -0 40 30 {lab=DOWN}
N 290 -20 290 40 {lab=VSS}
N 130 -50 130 70 {lab=IREF}
N -150 -110 -150 70 {lab=P_UP}
N -90 70 10 70 {lab=VCTRL}
N -190 110 -120 110 {lab=UP_B}
N -190 40 -190 110 {lab=UP_B}
N -250 -60 -120 -60 {lab=VDD}
N -250 -250 -250 -60 {lab=VDD}
N -120 -60 -120 70 {lab=VDD}
N 70 70 70 100 {lab=N_DOWN}
N 70 100 170 100 {lab=N_DOWN}
C {sg13cmos5l_pr/sg13_lv_pmos.sym} -220 60 3 0 {name=M_UP_INV_P
l=0.13u
w=0.30u
ng=1
m=1
mm_ok=1
model=sg13_lv_pmos
spiceprefix=X
}
C {sg13cmos5l_pr/sg13_lv_nmos.sym} -220 180 1 0 {name=M_UP_INV_N
l=0.13u
w=0.15u
ng=1
m=1
mm_ok=1
model=sg13_lv_nmos
spiceprefix=X
}
C {sg13cmos5l_pr/sg13_lv_nmos.sym} 150 -20 0 0 {name=M_IREF
l=0.50u
w=4.0u
ng=4
m=1
mm_ok=1
model=sg13_lv_nmos
spiceprefix=X
}
C {sg13cmos5l_pr/sg13_lv_pmos.sym} 190 -220 0 0 {name=M_PBIAS
l=0.50u
w=8.0u
ng=8
m=1
mm_ok=1
model=sg13_lv_pmos
spiceprefix=X
}
C {sg13cmos5l_pr/sg13_lv_nmos.sym} 150 -120 0 0 {name=M_PBIAS_SINK
l=0.50u
w=4.0u
ng=4
m=1
mm_ok=1
model=sg13_lv_nmos
spiceprefix=X
}
C {sg13cmos5l_pr/sg13_lv_pmos.sym} -130 -140 0 1 {name=M_UP_SOURCE
l=0.50u
w=7.0u
ng=8
m=1
mm_ok=1
model=sg13_lv_pmos
spiceprefix=X
}
C {sg13cmos5l_pr/sg13_lv_pmos.sym} -120 90 3 0 {name=M_UP_SWITCH
l=0.13u
w=1.0u
ng=1
m=1
mm_ok=1
model=sg13_lv_pmos
spiceprefix=X
}
C {sg13cmos5l_pr/sg13_lv_nmos.sym} 40 50 3 1 {name=M_DOWN_SWITCH
l=0.13u
w=1.5u
ng=1
m=1
mm_ok=1
model=sg13_lv_nmos
spiceprefix=X
}
C {sg13cmos5l_pr/sg13_lv_nmos.sym} 150 70 2 1 {name=M_DOWN_SINK
l=0.50u
w=4.0u
ng=4
m=1
mm_ok=1
model=sg13_lv_nmos
spiceprefix=X
}
C {ipin.sym} -300 120 2 1 {name=p_UP lab=UP}
C {ipin.sym} 40 0 1 0 {name=p_DOWN lab=DOWN}
C {iopin.sym} 130 -80 2 0 {name=p_IREF lab=IREF}
C {opin.sym} -40 70 1 1 {name=p_VCTRL lab=VCTRL}
C {iopin.sym} -250 -60 0 1 {name=p_VDD lab=VDD}
C {iopin.sym} 290 80 0 0 {name=p_VSS lab=VSS}
C {lab_wire.sym} -190 110 1 1 {name=UP_B sig_type=std_logic lab=UP_B}
C {lab_wire.sym} -150 -20 3 0 {name=P_UP1 sig_type=std_logic lab=P_UP}
C {lab_wire.sym} 110 100 1 1 {name=N_DOWN sig_type=std_logic lab=N_DOWN}
C {lab_wire.sym} 170 -190 0 0 {name=PBIAS sig_type=std_logic lab=PBIAS}
