// Copyright (c) 2024 Keegan Dent
//
// This source describes Open Hardware and is licensed under the CERN-OHL-W v2
// You may redistribute and modify this documentation and make products using
// it under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).
//
// This documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
// INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
// PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.

package processor_config;
    import source_config::*;
    import sink_config::*;

    parameter int RUN_WIDTH = SPK_WIDTH;
    parameter int INSTR_WIDTH = `SRC_WIDTH;
endpackage

import processor_config::*;

// This processor is a simple example that may be useful when two conditions are met:
// 1. The instruction is valid for every clock cycle.
// 2. The user is ready for output on every clock cycle.

module basic_processor (
    input logic clk,
    input logic arstn,
    input logic [INSTR_WIDTH-1:0] instr,
    output logic [NET_NUM_OUT-1:0] out
);
    logic net_valid;
    logic net_ready;

    network_source #(
        .RUN_WIDTH
    ) source (
        .clk(clk),
        .arstn(arstn),
        .src_valid(1),
        .src(instr),
        .net_ready,
        .net_valid
    );

    network net (
        .clk(clk),
        .arstn(source.net_arstn),
        .en(net_valid && net_ready),
        .inp(source.net_inp)
    );

    network_sink sink (
        .clk(clk),
        .arstn(arstn),
        .net_valid,
        .net_ready,
        .net_out(net.out),
        .snk_ready(1),
        .snk(out)
    );

endmodule