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
        NOM = 0,
        CLR
    } src_opcode_t;
    localparam int SRC_OPC_WIDTH = 1;
    // important to note that a NET_NUM_INP of 1 would make the spk width = charge width
    localparam int SRC_SPK_WIDTH = NET_NUM_INP * NET_CHARGE_WIDTH;
endpackage

module network_source
import source_config::*;
#(
    parameter int SRC_RUN_WIDTH // unused
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
    output logic net_last,  // unused
    // network signals
    output logic net_arstn,
    output logic signed [NET_CHARGE_WIDTH-1:0] net_inp [0:NET_NUM_INP-1]
);
    assign net_valid = src_valid;
    assign net_last = 0;
    assign src_ready = net_ready;

    // "Now watch this (half-clock) drive!"
    logic rst_p, rst_n;
    assign rst_p = src_valid && net_ready && (opcode_t'(src[(`SRC_WIDTH - 1) -: SRC_OPC_WIDTH]) == CLR);

    always_ff @(negedge clk or negedge arstn) begin : nset_rstn
        if (arstn == 0) begin
            rst_n <= 0;
        end else begin
            rst_n <= rst_p;
        end
    end
    assign net_arstn = (arstn == 0) ? 0 : !(rst_p && !rst_n);

    always_comb begin: calc_net_inp
        for (int i = 0; i < NET_NUM_INP; i++)
            net_inp[i] = src[(`SRC_WIDTH - SRC_OPC_WIDTH - (i * NET_CHARGE_WIDTH) - 1) -: NET_CHARGE_WIDTH];
    end
endmodule
