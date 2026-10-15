# LibreLane's normal setup/hold checker does not gate clock pulse width.
# Check the extracted design at each sign-off corner through its native hook.
if {$::env(STEP_ID) eq "OpenROAD.STAPostPNR"} {
    set channel [file tempfile clock_limits_path]
    close $channel
    report_check_types -min_pulse_width -min_period -verbose > $clock_limits_path
    set channel [open $clock_limits_path r]
    set clock_limits_report [read $channel]
    close $channel
    file delete $clock_limits_path

    puts "%OL_CREATE_REPORT clock-limits.rpt"
    puts $clock_limits_report
    puts "%OL_END_REPORT"
    if {[string first "(VIOLATED)" $clock_limits_report] >= 0} {
        error "Clock pulse-width/minimum-period violation at $corner_name"
    }
}
