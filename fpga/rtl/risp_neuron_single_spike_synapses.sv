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
    parameter int DELAYS [0:NUM_INP-1],
    parameter int MAX_OUTGOING_DELAY,
    parameter int LAST_FIRE_TIME_WIDTH,
    parameter int MAX_LAST_FIRE_TIME_WIDTH,
    parameter int CHARGE_WIDTH,
    parameter int POTENTIAL_MIN,
    parameter bit THRESHOLD_INCLUSIVE=1,
    parameter bit FIRE_LIKE_RAVENS=0
) (
    input logic clk,
    input logic arstn,
    input logic en,
    input logic signed [CHARGE_WIDTH-1:0] weights [0:NUM_INP-1],
    input logic signed [MAX_LAST_FIRE_TIME_WIDTH-1:0] last_fire_times [0:NUM_INP-1],
    output logic signed [LAST_FIRE_TIME_WIDTH-1:0] last_fire_time,
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

    logic do_fire;

    always_comb begin: calc_do_fire
        // determine if neuron fires this cycle
        sum = LEAK ? FUSE_START : fuse;
        for (int i = 0; i < NUM_INP; i++) begin
            if (last_fire_times[i] == DELAYS[i]) begin
                sum -= weights[i];
            end
        end
        do_fire = (sum <= 0) & (last_fire_time == -1 || last_fire_time == MAX_OUTGOING_DELAY);
    end

    always_ff @(posedge clk or negedge arstn) begin: set_fuse
        if (arstn == 0) begin
            fuse <= FUSE_START;
        end else if (en) begin
            if (do_fire) begin
                fuse <= FUSE_START;
            end else begin
                fuse <= `min(sum, FUSE_MAX);
            end
        end
    end

    always_ff @(posedge clk or negedge arstn) begin: last_fire_time_update
        if (arstn == 0) begin
            last_fire_time <= -1;
        end else if (en) begin
            if (MAX_OUTGOING_DELAY < 1) begin
                last_fire_time <= -1;
            end else if (fire == 1 && FIRE_LIKE_RAVENS == 0) begin
                last_fire_time <= 1;
            end else if (do_fire == 1 && FIRE_LIKE_RAVENS == 1) begin
                last_fire_time <= 1;
            end else if (last_fire_time == MAX_OUTGOING_DELAY) begin
                last_fire_time <= -1;
            end else if (last_fire_time != -1) begin
                last_fire_time <= last_fire_time + 1;
            end else begin
                last_fire_time <= -1;
            end
        end
    end

    generate
        if (FIRE_LIKE_RAVENS) begin
            always_ff @(posedge clk or negedge arstn) begin: set_fire
                if (arstn == 0) begin
                    fire <= 0;
                end else if (en) begin
                    fire <= do_fire;
                end
            end
        end else begin
            assign fire = do_fire;
        end
    endgenerate

endmodule
