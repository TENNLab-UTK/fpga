// Copyright (c) 2024 Keegan Dent
//
// This source describes Open Hardware and is licensed under the CERN-OHL-W v2
// You may redistribute and modify this documentation and make products using
// it under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).
//
// This documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
// INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
// PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.

`include "macros.svh"

module risp_neuron #(
    parameter int THRESHOLD,
    parameter bit LEAK,
    parameter int NUM_INP,
    parameter int CHARGE_WIDTH,
    parameter int POTENTIAL_MIN,
    parameter bit THRESHOLD_INCLUSIVE=1,
    parameter bit FIRE_LIKE_RAVENS=0    // TODO Implement
) (
    input logic clk,
    input logic arstn,
    input logic en,
    input logic signed [CHARGE_WIDTH-1:0] inp [0:NUM_INP-1],
    output logic fire
);
    localparam FUSE_START = THRESHOLD + !THRESHOLD_INCLUSIVE;
    localparam FUSE_MAX = FUSE_START - POTENTIAL_MIN;
    localparam FUSE_WIDTH = $clog2(FUSE_MAX + 1);
    // NOTE: simplification of $clog2(NUM_INP * (1 << (CHARGE_WIDTH - 1)) + (1 << FUSE_WIDTH))
    localparam SUM_WIDTH = CHARGE_WIDTH + $clog2(NUM_INP + (1 << (FUSE_WIDTH - CHARGE_WIDTH + 1)));

    // NOTE: "fuse" is THRESHOLD + !THRESHOLD_INCLUSIVE - potential
    logic [FUSE_WIDTH-1:0] fuse;
    logic signed [SUM_WIDTH-1:0] sum;

    always_comb begin: calc_fire
        // determine if neuron fires this cycle
        sum = LEAK ? FUSE_START : fuse;
        foreach(inp[i]) sum -= inp[i];
        fire = sum <= 0;
    end

    always_ff @(posedge clk or negedge arstn) begin: set_fuse
        if (arstn == 0) begin
            fuse <= FUSE_START;
        end else if (en) begin
            if (fire) begin
                fuse <= FUSE_START;
            end else begin
                fuse <= `min(sum, FUSE_MAX);
            end
        end
    end
endmodule