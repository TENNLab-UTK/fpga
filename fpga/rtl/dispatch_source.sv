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

package source_config;
    import network_config::*;

    typedef enum {
        NOP = 0,
        RUN,
        SPK,
        CLR,
        NUM_OPS   // not a valid opcode, purely for counting
    } opcode_t;
    localparam int OPC_WIDTH = $clog2(NUM_OPS);
    // important to note that a NET_NUM_INP of 1 would make the spk width = charge width
    localparam int SPK_WIDTH = $clog2(NET_NUM_INP) + NET_CHARGE_WIDTH;
endpackage

import source_config::*;

module network_source #(
    parameter int RUN_WIDTH
) (
    // global inputs
    input logic clk,
    input logic arstn,
    // source handshake signals
    input logic src_valid,
    output logic src_ready,
    // source input
    input logic [`SRC_WIDTH-1:0] src,
    // network handshake signals
    input logic net_ready,
    output logic net_valid,
    // network signals
    output logic net_arstn,
    output logic signed [NET_CHARGE_WIDTH-1:0] net_inp [0:NET_NUM_INP-1]
);
    opcode_t op;

    always_comb begin : calc_op
        if (src_valid && src_ready)
            op = opcode_t'(src[(`SRC_WIDTH - 1) -: OPC_WIDTH]);
        else
            op = NOP;
    end

    logic [RUN_WIDTH-1:0] run_counter;
    assign src_ready = (run_counter <= 1);
    assign net_valid = (run_counter > 0);

    always_ff @(posedge clk or negedge arstn) begin: set_run_counter
        if (arstn == 0) begin
            run_counter <= 0;
        end else begin
            if (op == RUN) begin
                // RUN op with a '0' run value is assumed to be a single cycle
                run_counter <= `max(src[(`SRC_WIDTH - OPC_WIDTH - 1) -: RUN_WIDTH], 1);
            end else if (net_valid && net_ready) begin
                run_counter <= run_counter - 1;
            end
        end
    end

    logic [$clog2(NET_NUM_INP + 1) - 1 : 0] inp_idx;
    generate
        if (SPK_WIDTH == NET_CHARGE_WIDTH)
            assign inp_idx = 0;
        else
            assign inp_idx = src[(`SRC_WIDTH - OPC_WIDTH - 1) -: $clog2(NET_NUM_INP)];
    endgenerate

    logic signed [NET_CHARGE_WIDTH-1:0] inp_val;
    assign inp_val = src[(`SRC_WIDTH - OPC_WIDTH - $clog2(NET_NUM_INP) - 1) -: NET_CHARGE_WIDTH];

    always_ff @(posedge clk or negedge arstn) begin: set_net_inp
        if (arstn == 0) begin
            net_arstn <= 0;
            for (int i = 0; i < NET_NUM_INP; i++)
                net_inp[i] <= 0;
        end else if (op == CLR) begin   // Quartus synthesis demands this be a separate conditional block
            net_arstn <= 0;
            for (int i = 0; i < NET_NUM_INP; i++)
                net_inp[i] <= 0;
        end else begin
            net_arstn <= 1;
            if (op == SPK) begin
                // set inputs on a spike dispatch
                net_inp[inp_idx] <= inp_val;
            end else if (net_valid) begin
                // reset inputs every time network is run
                for (int i = 0; i < NET_NUM_INP; i++)
                    net_inp[i] <= 0;
            end
        end
    end

endmodule