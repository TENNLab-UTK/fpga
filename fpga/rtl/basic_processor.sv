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

package processor_config;
    parameter int INP_WIDTH = source_config::PFX_WIDTH + `max(source_config::SPK_WIDTH, 1);
    parameter int OUT_WIDTH = sink_config::PFX_WIDTH + `max(sink_config::SPK_WIDTH, 1);
endpackage

// This processor is a simple example that may be useful when two conditions are met:
// 1. The instruction is valid for every clock cycle.
// 2. The user is ready for output on every clock cycle.

module basic_processor (
    input logic clk,
    input logic arstn,
    input logic [processor_config::INP_WIDTH-1:0] inp,
    output logic [processor_config::OUT_WIDTH-1:0] out
);
    import processor_config::*;
    logic lnk_valid, net_ready, net_sync;

    network_source #(
        .PKT_WIDTH(INP_WIDTH)
    ) source (
        .clk(clk),
        .arstn(arstn),
        .src_valid(1),
        .src(inp),
        .net_ready,
        .net_sync
    );

    network net (
        .clk(clk),
        .arstn(source.net_arstn),
        .en(source.net_en),
        .inp(source.net_inp)
    );

    network_sink sink #(
        .PKT_WIDTH(OUT_WIDTH)
    ) (
        .clk(clk),
        .arstn,
        .net_sync,
        .net_ready,
        .net_arstn(source.net_arstn),
        .net_en(source.net_en),
        .net_out(net.out),
        .snk_ready(1),
        .snk(out)
    );
endmodule
