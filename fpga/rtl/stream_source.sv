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
    // network signals
    input logic net_ready,
    output logic net_run,
    output logic net_sync,
    output logic net_clear,
    output logic signed [network_config::CHARGE_WIDTH-1:0] net_inp [0:network_config::NUM_INP-1]
);
    import network_config::*;
    import stream_config::*;
    import source_config::*;

    assign src_ready = net_ready;
    assign net_run = src_valid;
    assign net_sync = src_valid ? src[PKT_WIDTH - SNC - 1] : 0;
    assign net_clear = src_valid ? src[PKT_WIDTH - CLR - 1] : 0;

    always_comb begin: calc_net_inp
        for (int i = 0; i < NUM_INP; i++)
            net_inp[i] = src[(PKT_WIDTH - PFX_WIDTH - (i * CHARGE_WIDTH) - 1) -: CHARGE_WIDTH];
    end
endmodule
