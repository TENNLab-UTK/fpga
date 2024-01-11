// Copyright (c) 2024 Keegan Dent
//
// This source describes Open Hardware and is licensed under the CERN-OHL-W v2
// You may redistribute and modify this documentation and make products using
// it under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).
//
// This documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
// INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
// PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.

module risp_neuron #(
    parameter int THRESHOLD,
    parameter bit LEAK,
    parameter int NUM_INP,
    parameter int CHARGE_WIDTH,
    parameter bit THRESHOLD_INCLUSIVE=1,
    parameter bit NON_NEGATIVE_POTENTIAL=0,
    parameter bit FIRE_LIKE_RAVENS=0    // TODO Implement
) (
    input logic clk,
    input logic arstn,
    input logic en,
    input logic signed [CHARGE_WIDTH-1:0] inp [0:NUM_INP-1],
    output logic fire
);
    localparam POTENTIAL_ABS_MAX = ((THRESHOLD < 0) ? -THRESHOLD : THRESHOLD) + !THRESHOLD_INCLUSIVE;
    localparam POTENTIAL_WIDTH = $clog2(POTENTIAL_ABS_MAX) + 1; // sign bit
    localparam SUM_WIDTH = $clog2(NUM_INP * ((1 << (CHARGE_WIDTH - 2)) - 1) + POTENTIAL_ABS_MAX) + 1;

    logic signed [POTENTIAL_WIDTH-1:0] potential;
    logic signed [SUM_WIDTH-1:0] sum;

    always_comb begin: calc_fire
        // determine if neuron fires this cycle
        sum = (LEAK || (NON_NEGATIVE_POTENTIAL && (potential < 0))) ? 0 : potential;
        foreach(inp[i]) sum += inp[i];
        fire = sum >= (THRESHOLD + !THRESHOLD_INCLUSIVE);
    end

    always_ff @(posedge clk or negedge arstn) begin: set_potential
        if (arstn == 0) begin
            potential <= 0;
        end else if (en) begin
            if (fire) begin
                potential <= 0;
            end else begin
                potential <= sum;
            end
        end
    end
endmodule