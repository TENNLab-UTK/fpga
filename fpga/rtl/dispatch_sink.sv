// Copyright (c) 2024 Keegan Dent
//
// This source describes Open Hardware and is licensed under the CERN-OHL-W v2
// You may redistribute and modify this documentation and make products using
// it under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).
//
// This documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
// INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
// PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.

package sink_config;
    import network_config::*;

    typedef enum {
        RUN,
        SPK,
        NUM_OPS   // not a valid opcode, purely for counting
    } opcode_t;
    localparam int SNK_OPC_WIDTH = $clog2(NUM_OPS);
    // important to note that a NET_NUM_OUT of 1 would make the spk width = 0, making out_idx implicit
    localparam int SNK_SPK_WIDTH = $clog2(NET_NUM_OUT);
endpackage

import sink_config::*;

module network_sink #(
    parameter int SNK_RUN_WIDTH
) (
    // global inputs
    input logic clk,
    input logic arstn,
    // network handshake signals
    input logic net_valid,
    output logic net_ready,
    // network signals
    input logic [NET_NUM_OUT-1:0] net_out,
    // sink handshake signals
    input logic snk_ready,
    output logic snk_valid,
    // sink output
    output logic [`SNK_WIDTH-1:0] snk
);
    logic [SNK_RUN_WIDTH-1:0] run_counter, runs;

    always_ff @(posedge clk or negedge arstn) begin: set_run_counter
        if (arstn == 0) begin
            run_counter <= 0;
        end else if (net_valid && net_ready) begin
            if (|net_out || &run_counter) begin
                run_counter <= 0;
            end else begin
                run_counter <= run_counter + 1;
            end
        end
    end

    logic [NET_NUM_OUT-1:0] fires;

    always_ff @(posedge clk or negedge arstn) begin: set_fires_runs
        if (arstn == 0) begin
            fires <= 0;
            runs <= 0;
        end else if (net_valid && net_ready) begin
            fires <= net_out;
            runs <= run_counter;
        end
    end

    logic [$clog2(NET_NUM_OUT + 1)-1:0] snk_counter;
    assign net_ready = snk_counter == 0;

    always_ff @(posedge clk or negedge arstn) begin: set_snk_counter
        if (arstn == 0) begin
            snk_counter <= 0;
        end else begin
            if (net_valid && net_ready && (|net_out || &run_counter)) begin
                snk_counter <= NET_NUM_OUT + (run_counter > 0);
            end else if (snk_ready) begin
                if ((snk_counter > 0) && |fires) begin
                    snk_counter <= snk_counter - 1;
                end else begin
                    snk_counter <= 0;
                end
            end
        end
    end

    always_comb begin: calc_snk
        snk[`SNK_WIDTH-1:0] = 0;
        snk_valid = 0;
        if (snk_counter == NET_NUM_OUT + 1) begin
            snk[(`SNK_WIDTH - 1) -: SNK_OPC_WIDTH] = RUN;
            snk[(`SNK_WIDTH - SNK_OPC_WIDTH - 1) -: SNK_RUN_WIDTH] = runs;
            snk_valid = 1;
        end else if (snk_counter > 0) begin
            snk[(`SNK_WIDTH - 1) -: SNK_OPC_WIDTH] = SPK;
            snk[(`SNK_WIDTH - SNK_OPC_WIDTH - 1) -: SNK_SPK_WIDTH] = NET_NUM_OUT - snk_counter;
            snk_valid = fires[NET_NUM_OUT - snk_counter];
        end
    end
endmodule
