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

package processor_config;
    localparam int PROC_WIDTH_BYTES = 1;
    localparam int INP_WIDTH = `width_bytes_to_bits(PROC_WIDTH_BYTES);
    localparam int OUT_WIDTH = `width_bytes_to_bits(PROC_WIDTH_BYTES);
    localparam int OUT_PER_RUN_MAX = 1;
    localparam int RUN_MAX_BASE = 1;
    localparam int RUN_WIDTH = 1;
endpackage

module axis_processor
(
    input logic clk,
    input logic arstn,
    input logic [processor_config::INP_WIDTH-1:0] s_axis_tdata,
    input logic s_axis_tvalid,
    output logic s_axis_tready,
    output logic [processor_config::OUT_WIDTH-1:0] m_axis_tdata,
    output logic m_axis_tvalid,
    input logic m_axis_tready
);
    import processor_config::*;

    assign s_axis_tready = m_axis_tready;
    assign m_axis_tvalid = s_axis_tvalid;
    assign m_axis_tdata = s_axis_tdata;
endmodule
