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

    localparam int RUN_WIDTH = `width_nearest_byte(SPK_WIDTH + OPC_WIDTH) - OPC_WIDTH;
    localparam int INP_WIDTH = `SRC_WIDTH;
    localparam int OUT_WIDTH = `width_nearest_byte(SNK_WIDTH);
endpackage

import processor_config::*;
import network_config::*;

module axis_processor (
    input logic clk,
    input logic arstn,
    axis.s s_axis,
    axis.m m_axis
);
    logic net_valid, net_ready;
    logic [NET_NUM_OUT-1:0] net_out;

    network_source #(
        .RUN_WIDTH(RUN_WIDTH)
    ) source (
        .clk,
        .arstn,
        .src_valid(s_axis.tvalid),
        .src_ready(s_axis.tready),
        .src(s_axis.tdata[(INP_WIDTH - 1) -: `SRC_WIDTH]),
        .net_ready,
        .net_valid
    );

    network net (
        .clk,
        .arstn(source.net_arstn),
        .en(net_valid && net_ready),
        .inp(source.net_inp),
        .out(net_out)
    );

    network_sink sink (
        .clk,
        .arstn,
        .net_valid,
        .net_ready,
        .net_out,
        .snk_ready(m_axis.tready),
        .snk_valid(m_axis.tvalid)
    );

    always_comb begin : calc_m_axis_tdata
        m_axis.tdata[OUT_WIDTH-1:0] = 0;
        m_axis.tdata[(OUT_WIDTH - 1) -: SNK_WIDTH] = sink.snk;
    end
endmodule