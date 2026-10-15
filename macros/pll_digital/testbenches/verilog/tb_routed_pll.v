`timescale 1ns/1ps
module tb_routed_pll;
    reg vco_clk = 0, ref_clk = 0, reset_n = 0, enable = 0;
    reg [9:0] div_ratio = 32;
    reg [1:0] test_div_select = 0;
    wire feedback_clk, pll_clk, test_clk, up, down;
    pll_digital dut (.*);
    always #0.25 vco_clk = ~vco_clk;
    always #5 ref_clk = ~ref_clk;

    task restart;
        begin
            @(negedge vco_clk);
            reset_n = 0;
            enable = 1;
            #0.001;
            if ({feedback_clk, pll_clk, test_clk, up, down} !== 5'b0)
                $fatal(1, "Asynchronous reset did not clear outputs");
            repeat (4) @(negedge vco_clk);
            reset_n = 1;
        end
    endtask

    integer n, frac, pulses, cycles, previous_cycle, interval;
    integer sum, minimum, maximum, code, mode, edges;
    reg previous_feedback, previous_test;
    initial begin
        // Independent output-rate checks exercise all four mux selections.
        for (mode = 0; mode < 4; mode = mode + 1) begin
            test_div_select = mode;
            restart;
            edges = 0;
            previous_test = 0;
            repeat (256) begin
                @(posedge vco_clk);
                #0.001;
                if (test_clk === 1'b1 && previous_test === 1'b0)
                    edges = edges + 1;
                if (test_clk !== 0 && test_clk !== 1)
                    $fatal(1, "Unknown output clock");
                previous_test = test_clk;
            end
            if (edges != (128 >> mode))
                $fatal(1, "Output mode %0d: %0d edges", mode, edges);
            $display("PASS OUTPUT MODE %0d", mode);
        end

        // All Q7.3 ratios; 16 intervals span a complete carry schedule.
        for (n = 4; n <= 127; n = n + 1) begin
            for (frac = 0; frac < 8; frac = frac + 1) begin
                @(negedge vco_clk);
                reset_n = 0;
                div_ratio = n * 8 + frac;
                restart;
                pulses = 0; cycles = 0; previous_cycle = 0;
                sum = 0; minimum = 1000000; maximum = 0;
                previous_feedback = 0;
                while (pulses < 17) begin
                    @(posedge pll_clk);
                    #0.001;
                    cycles = cycles + 1;
                    if (feedback_clk !== 0 && feedback_clk !== 1)
                        $fatal(1, "Unknown feedback N=%0d frac=%0d", n, frac);
                    if (feedback_clk && !previous_feedback) begin
                        if (pulses > 0) begin
                            interval = cycles - previous_cycle;
                            sum = sum + interval;
                            if (interval < minimum) minimum = interval;
                            if (interval > maximum) maximum = interval;
                        end
                        previous_cycle = cycles;
                        pulses = pulses + 1;
                    end
                    previous_feedback = feedback_clk;
                    if (cycles > 17 * (n + 2))
                        $fatal(1, "Divider stalled N=%0d frac=%0d", n, frac);
                end
                code = n * 8 + frac;
                if (sum != code || minimum != code / 16 ||
                    maximum != (code + 15) / 16)
                    $fatal(1, "Ratio N=%0d frac=%0d sum=%0d min=%0d max=%0d",
                           n, frac, sum, minimum, maximum);
                $display("PASS ROUTED N=%0d frac=%0d", n, frac);
            end
        end
        @(negedge vco_clk);
        enable = 0;
        #0.001;
        if ({feedback_clk, pll_clk, test_clk, up, down} !== 5'b0)
            $fatal(1, "Disable did not clear outputs");
        $display("ALL ROUTED FUNCTIONAL TESTS PASSED (NO SDF)");
        $finish;
    end
    initial begin
        #2000000;
        $fatal(1, "Watchdog expired");
    end
endmodule
