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

import processor_config::*;

module uart_processor #(
    parameter real CLK_FREQ,
    parameter int BAUD_RATE = 115_200
) (
    input logic clk,
    input logic arstn,
    input logic rxd,
    output logic txd,
    output logic rx_busy,
    output logic tx_busy,
    output logic rx_error
);
    // Do not change unless adding support for UART parameters outside 8N1 (likely never)
    localparam int UART_WIDTH = 8;

    logic [UART_WIDTH-1:0] rx_axis_tdata, tx_axis_tdata;
    logic rx_axis_tvalid, rx_axis_tready, tx_axis_tvalid, tx_axis_tready;
    logic rx_frame_error, rx_overrun_error;

    logic [15:0] prescale;
    assign prescale = int'($floor(CLK_FREQ / real'(UART_WIDTH * BAUD_RATE)));

    uart #(
        .DATA_WIDTH(UART_WIDTH)
    ) uart_inst (
        .clk,
        .arstn,
        .s_axis_tdata(tx_axis_tdata),
        .s_axis_tvalid(tx_axis_tvalid),
        .s_axis_tready(tx_axis_tready),
        .m_axis_tdata(rx_axis_tdata),
        .m_axis_tvalid(rx_axis_tvalid),
        .m_axis_tready(rx_axis_tready),
        .rxd,
        .txd,
        .rx_busy,
        .tx_busy,
        .rx_frame_error,
        .rx_overrun_error,
        .prescale
    );

    always_ff @(posedge clk or negedge arstn) begin : set_rx_erorr
        if (arstn == 0) begin
            rx_error <= 0;
        end else begin
            rx_error <= rx_error || rx_frame_error || rx_overrun_error;
        end
    end

    logic [INP_WIDTH-1:0] inp_axis_tdata;
    logic inp_axis_tvalid, inp_axis_tready;
    logic [OUT_WIDTH-1:0] out_axis_tdata;
    logic out_axis_tvalid, out_axis_tready;

    axis_processor proc (
        .clk,
        .arstn,
        .s_axis_tdata(inp_axis_tdata),
        .s_axis_tvalid(inp_axis_tvalid),
        .s_axis_tready(inp_axis_tready),
        .m_axis_tdata(out_axis_tdata),
        .m_axis_tvalid(out_axis_tvalid),
        .m_axis_tready(out_axis_tready)
    );

    axis_adapter #(
        .S_DATA_WIDTH(UART_WIDTH),
        .M_DATA_WIDTH(INP_WIDTH)
    )  rx_inp_adapter (
        .clk,
        .arstn,
        .s_axis_tdata(rx_axis_tdata),
        .s_axis_tvalid(rx_axis_tvalid),
        .s_axis_tready(rx_axis_tready),
        .m_axis_tdata(inp_axis_tdata),
        .m_axis_tvalid(inp_axis_tvalid),
        .m_axis_tready(inp_axis_tready)
    );

    axis_adapter #(
        .S_DATA_WIDTH(OUT_WIDTH),
        .M_DATA_WIDTH(UART_WIDTH)
    ) out_tx_adapter (
        .clk,
        .arstn,
        .s_axis_tdata(out_axis_tdata),
        .s_axis_tvalid(out_axis_tvalid),
        .s_axis_tready(out_axis_tready),
        .m_axis_tdata(tx_axis_tdata),
        .m_axis_tvalid(tx_axis_tvalid),
        .m_axis_tready(tx_axis_tready)
    );
endmodule