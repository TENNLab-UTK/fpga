// Copyright (c) 2024 Bryson Gullett
//
// This source describes Open Hardware and is licensed under the CERN-OHL-W v2
// You may redistribute and modify this documentation and make products using
// it under the terms of the CERN-OHL-W v2 (https:/cern.ch/cern-ohl).
//
// This documentation is distributed WITHOUT ANY EXPRESS OR IMPLIED WARRANTY,
// INCLUDING OF MERCHANTABILITY, SATISFACTORY QUALITY AND FITNESS FOR A
// PARTICULAR PURPOSE. Please see the CERN-OHL-W v2 for applicable conditions.

`include "macros.svh"

package processor_tlast_config;
    import processor_config::*;
    import sink_config::*;

    localparam int INP_TDATA_WIDTH_BYTES = `width_nearest_pow2_bytes(INP_WIDTH);
    localparam int OUT_TDATA_WIDTH_BYTES = `width_nearest_pow2_bytes(SNK_WIDTH+1);
endpackage

import processor_tlast_config::*;

module axis_processor_tlast (
    input logic clk,
    input logic arstn,
    axis.s s_axis,
    axis.m m_axis
);
    logic last_cycle, last_pkt;

    axis #(.DATA_WIDTH_BYTES(`width_bits_to_bytes(INP_WIDTH)), .ID_WIDTH(s_axis.ID_WIDTH), .DEST_WIDTH(s_axis.DEST_WIDTH), .USER_WIDTH(s_axis.USER_WIDTH)) s_axis_proc();
    axis #(.DATA_WIDTH_BYTES(`width_bits_to_bytes(OUT_WIDTH)), .ID_WIDTH(m_axis.ID_WIDTH), .DEST_WIDTH(m_axis.DEST_WIDTH), .USER_WIDTH(m_axis.USER_WIDTH)) m_axis_proc();

    // Connect AXIS slave signals to inner axis_processor
    assign s_axis_proc.tvalid = s_axis.tvalid;
    assign s_axis.tready = s_axis_proc.tready;
    assign s_axis_proc.tdata = s_axis.tdata[(INP_TDATA_WIDTH_BYTES*8)-1 -: INP_WIDTH];
    assign s_axis_proc.tstrb = s_axis.tstrb;
    assign s_axis_proc.tkeep = s_axis.tkeep;
    assign s_axis_proc.tlast = s_axis.tlast;
    assign s_axis_proc.tid = s_axis.tid;
    assign s_axis_proc.tdest = s_axis.tdest;
    assign s_axis_proc.tuser = s_axis.tuser;
    
    // Connect AXIS master signals to inner axis_processor, except for tdata, tvalid, tlast, tkeep
    // assign m_axis_proc.tvalid = m_axis.tvalid;
    assign m_axis_proc.tready = m_axis.tready;
    // assign m_axis_proc.tdata = m_axis.tdata;
    assign m_axis.tstrb = m_axis_proc.tstrb;
    // assign m_axis_proc.tkeep = m_axis.tkeep;
    // assign m_axis_proc.tlast = m_axis.tlast;
    assign m_axis.tid = m_axis_proc.tid;
    assign m_axis.tdest = m_axis_proc.tdest;
    assign m_axis.tuser = m_axis_proc.tuser;

    axis_processor axis_processor_0 (
        .clk,
        .arstn,
        .s_axis(s_axis_proc),
        .m_axis(m_axis_proc)
    );

    axis_packetize #(
        .PKT_SIZE(8),
        .MAX_CLK_CYCLES_PER_PKT(10)
    ) axis_packetize_0 (
        .clk,
        .arstn,
        .tvalid(m_axis.tvalid),
        .tready(m_axis.tready),
        .last_cycle,
        .last_pkt
    );

    assign m_axis.tvalid = last_cycle | m_axis_proc.tvalid;
    assign m_axis.tdata = {m_axis_proc.tvalid, m_axis_proc.tdata[$bits(m_axis_proc.tdata)-1 -: `min($bits(m_axis.tdata)-1, $bits(m_axis_proc.tdata))], {($bits(m_axis.tdata)-1-`min($bits(m_axis.tdata)-1, $bits(m_axis_proc.tdata))){1'b0}}};
    assign m_axis.tlast = last_cycle | (last_pkt & m_axis.tvalid);
    assign m_axis.tkeep = ~0;
endmodule