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

module axis_processor (
    input logic clk,
    input logic arstn,
    input logic [INP_WIDTH-1:0] s_axis_tdata,
    input logic s_axis_tvalid,
    output logic s_axis_tready,
    output logic [OUT_WIDTH-1:0] m_axis_tdata,
    output logic m_axis_tvalid,
    input logic m_axis_tready
);
    logic net_valid, net_ready, net_arstn;
    logic signed [NET_CHARGE_WIDTH-1:0] net_inp [0:NET_NUM_INP-1];
    logic [NET_NUM_OUT-1:0] net_out;

    network_source #(
        .RUN_WIDTH(RUN_WIDTH)
    ) source (
        .clk,
        .arstn,
        .src_valid(s_axis_tvalid),
        .src_ready(s_axis_tready),
        .src(s_axis_tdata[(INP_WIDTH - 1) -: `SRC_WIDTH]),
        .net_ready,
        .net_valid,
        .net_arstn,
        .net_inp
    );

    network net (
        .clk,
        .arstn(net_arstn),
        .en(net_valid && net_ready),
        .inp(net_inp),
        .out(net_out)
    );

    logic [SNK_WIDTH-1:0] snk;

    network_sink sink (
        .clk,
        .arstn,
        .net_valid,
        .net_ready,
        .net_out,
        .snk_ready(m_axis_tready),
        .snk_valid(m_axis_tvalid),
        .snk
    );

    always_comb begin : calc_m_axis_tdata
        m_axis_tdata[OUT_WIDTH-1:0] = 0;
        m_axis_tdata[(OUT_WIDTH - 1) -: SNK_WIDTH] = snk;
    end
endmodule
