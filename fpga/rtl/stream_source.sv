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
        CLR = 0,
        DEC,
        NUM_OPS   // not a valid opcode, purely for counting
    } flag_t;
    localparam int OPC_WIDTH = NUM_OPS;
    // important to note that a NET_NUM_INP of 1 would make the spk width = charge width
    localparam int SPK_WIDTH = NET_NUM_INP * NET_CHARGE_WIDTH;
    localparam int SPK_PRDC_WIDTH = 0;
endpackage

import source_config::*;

module network_source #(
    parameter int RUN_WIDTH // unused
) (
    // global inputs
    input logic clk,
    input logic arstn,
    // source handshake signals
    input logic src_valid,
    output logic src_ready,
    // source input
    input logic [`SRC_WIDTH-1:0] src,
    // output handshake signal
    output logic out_ready,
    // network handshake signals
    input logic net_ready,
    output logic net_valid,
    // network signals
    output logic net_clr,
    output logic signed [NET_CHARGE_WIDTH-1:0] net_inp [0:NET_NUM_INP-1]
);

    logic has_clr, has_dec, delay;

    assign has_clr = src[`SRC_WIDTH - CLR - 1];
    assign has_dec = src[`SRC_WIDTH - DEC - 1];

    assign net_valid = src_valid & ((~has_clr & ~has_dec) | delay);
    assign src_ready = net_ready & ((~has_clr & ~has_dec) | delay);
    assign out_ready = src_valid & has_dec & ~delay;

    assign net_clr = src_valid & net_ready & has_clr & ~delay;

    always_comb begin: calc_net_inp
        for (int i = 0; i < NET_NUM_INP; i++)
            net_inp[i] = src[(`SRC_WIDTH - OPC_WIDTH - (i * NET_CHARGE_WIDTH) - 1) -: NET_CHARGE_WIDTH];
    end

    always_ff @(posedge clk or negedge arstn) begin: set_delay
        if (arstn == 0) begin
            delay <= 0;
        end else if ((has_clr || has_dec) && !delay) begin
            delay <= 1;
        end else begin
            delay <= 0;
        end
    end


endmodule