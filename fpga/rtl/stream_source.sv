// Copyright (c) 2024-2025 Keegan Dent
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
    export *::*;
    import network_config::*;
    import stream_config::*;
    localparam int PFX_WIDTH = NUM_FLG;
    localparam int SPK_WIDTH = NUM_INP * CHARGE_WIDTH;
endpackage

module network_source #(
    parameter int PKT_WIDTH
) (
    // global inputs
    input logic clk,
    input logic arstn,
    // source handshake signals
    input logic src_valid,
    output logic src_ready,
    // source input
    input logic [PKT_WIDTH-1:0] src,
    // network handshake signals
    input logic net_ready,
    output logic net_valid,
    output logic net_last,
    // network signals
    output logic net_arstn,
    output logic signed [network_config::CHARGE_WIDTH-1:0] net_inp [0:network_config::NUM_INP-1]
);
    import stream_config::*;
    import source_config::*;

    assign net_valid = src_valid;
    assign src_ready = net_ready;

    assign net_last = src[PKT_WIDTH - FIN - 1];

    // "Now watch this (half-clock) drive!"
    logic rst_p, rst_n;
    // rst_p asserted for one clock at positive edge when CLR
    assign rst_p = src_valid && net_ready && src[PKT_WIDTH - CLR - 1];

    // rst_n is rst_p delayed by a half-clock
    always_ff @(negedge clk or negedge arstn) begin : nset_rstn
        if (arstn == 0) begin
            rst_n <= 0;
        end else begin
            rst_n <= rst_p;
        end
    end

    // net_arstn is asserted low when artsn is low
    // or for the half-clock when rst_p is asserted and rst_n is not asserted
    assign net_arstn = (arstn == 0) ? 0 : !(rst_p && !rst_n);

    always_comb begin: calc_net_inp
        for (int i = 0; i < NUM_INP; i++)
            net_inp[i] = src[(PKT_WIDTH - PFX_WIDTH - (i * CHARGE_WIDTH) - 1) -: CHARGE_WIDTH];
    end
endmodule
