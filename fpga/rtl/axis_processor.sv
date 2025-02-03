// Copyright (c) 2024-2025 Keegan Dent
//
// This source describes Open Hardware and is licensed under the CERN-OHL-W v2
// You may redistribute and modify this documentation and make products using
// it under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).
//
// This documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
// INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
// PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.

package processor_config;
    import network_config::*;

    localparam int SRC_PKT_WIDTH = `width_nearest_byte(source_config::PFX_WIDTH + source_config::SPK_WIDTH);
    localparam int INP_WIDTH = SRC_PKT_WIDTH;

    localparam int SNK_PKT_WIDTH = `width_nearest_byte(sink_config::PFX_WIDTH + sink_config::SPK_WIDTH);
    localparam int OUT_WIDTH = SNK_PKT_WIDTH;
endpackage

module axis_processor (
    input logic clk,
    input logic arstn,
    input logic [processor_config::INP_WIDTH-1:0] s_axis_tdata,
    input logic s_axis_tvalid,
    output logic s_axis_tready,
    output logic [processor_config::OUT_WIDTH-1:0] m_axis_tdata,
    output logic m_axis_tvalid,
    input logic m_axis_tready
);
    import network_config::*;
    import processor_config::*;

    logic net_ready, net_sync, net_arstn, net_en;
    logic signed [CHARGE_WIDTH-1:0] net_inp [0:NUM_INP-1];
    logic [NUM_OUT-1:0] net_out;

    network_source #(
        .PKT_WIDTH(SRC_PKT_WIDTH)
    ) source (
        .clk,
        .arstn,
        .src_valid(s_axis_tvalid),
        .src_ready(s_axis_tready),
        .src(s_axis_tdata[(INP_WIDTH - 1) -: SRC_PKT_WIDTH]),
        .net_ready,
        .net_sync,
        .net_en,
        .net_arstn,
        .net_inp
    );

    network net (
        .clk,
        .arstn(net_arstn),
        .en(net_en),
        .inp(net_inp),
        .out(net_out)
    );

    logic [SNK_PKT_WIDTH-1:0] snk;

    network_sink #(
        .PKT_WIDTH(SNK_PKT_WIDTH)
    ) sink (
        .clk,
        .arstn,
        .net_sync,
        .net_ready,
        .net_out,
        .net_arstn,
        .net_en,
        .snk_ready(m_axis_tready),
        .snk_valid(m_axis_tvalid),
        .snk
    );

    always_comb begin : calc_m_axis_tdata
        m_axis_tdata[OUT_WIDTH-1:0] = 0;
        m_axis_tdata[(OUT_WIDTH - 1) -: SNK_PKT_WIDTH] = snk;
    end
endmodule
