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
    parameter int BRAM_BITS = 1_843_200,
    parameter int BAUD_RATE = 115_200,
    parameter int HOST_BUFFER = 4096
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
    localparam int UART_PADS = 2;

    logic [UART_WIDTH-1:0] rx_axis_tdata, tx_axis_tdata;
    logic rx_axis_tvalid, rx_axis_tready, tx_axis_tvalid, tx_axis_tready;
    logic rx_frame_error, rx_overrun_error;

    uart #(
        .CLK_FREQ(CLK_FREQ),
        .BAUD_RATE(BAUD_RATE),
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
        .rx_overrun_error
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

    // we buffer the rx side because there is no way of conveying backpressure to the host
    // we don't buffer the tx side because the host has a buffer and the UART tx module exerts backpressure
    // the question becomes how do we size the buffer?
    // we need to anticipate how many packets we could receive while the processor is transmitting
    // - for a Dispatch Source
    //   - take the number of runs supported by the operand width (2 ^ run_width - 1)
    //   - multiply by the amount of time per run (further below)
    //   - divide by the time per packet (10 buad/byte * (out_width / 8) / baud_rate)
    // - for a Stream Source, for a Stream Source, the strategy is to mirror the size of the linux host buffer: 4096 bytes
    // the worst case run latency is driven by the UART baud rate, the system clock speed, and the sink mechanism
    // for Dispatch Sink it's the sum of:
    // - one clock per net_out
    // - ten baud per byte; max_bytes is (net_out + 1) * (out_width / 8)
    // for Stream Sink it's again ten baud per byte; max_bytes is (out_width / 8)

    // UART character rate
    localparam real CHAR_RATE = real'(BAUD_RATE) / real'(UART_WIDTH + UART_PADS);
    // clock cycle per character actually transmitted
    localparam real CLK_PER_CHAR = CLK_FREQ / CHAR_RATE;

    localparam int OUT_CHAR_PER_RUN_MAX = (OUT_PER_RUN_MAX * OUT_WIDTH + UART_WIDTH - 1) / UART_WIDTH;
    localparam int RUN_MAX = `max(RUN_MAX_BASE ** RUN_WIDTH - 1, HOST_BUFFER / OUT_CHAR_PER_RUN_MAX);
    // maximum "RUN 1 time" for processor
    localparam int CLK_PER_RUN_MAX = `ceil(CLK_PER_CHAR) * OUT_CHAR_PER_RUN_MAX + OUT_PER_RUN_MAX - 1;
    // maximum "RUN X time" for processor
    localparam int CLK_MAX = CLK_PER_RUN_MAX * RUN_MAX;

    localparam int TARGET_BUF_DEPTH = `max(`cdiv(CLK_MAX, `floor(CLK_PER_CHAR)), HOST_BUFFER);
    localparam int BRAM_DEPTH = `next_pow2(BRAM_BITS >> 1) / UART_WIDTH;
    localparam int BUF_DEPTH = `min(TARGET_BUF_DEPTH, BRAM_DEPTH);

    logic [UART_WIDTH-1:0] buf_axis_tdata;
    logic buf_axis_tvalid, buf_axis_tready;

    axis_fifo #(
        .DATA_WIDTH(UART_WIDTH),
        .DEPTH(BUF_DEPTH),
        .KEEP_ENABLE(0),
        .LAST_ENABLE(0),
        .USER_ENABLE(0)
    ) rx_buf (
        .clk,
        .arstn,
        .s_axis_tdata(rx_axis_tdata),
        .s_axis_tvalid(rx_axis_tvalid),
        .s_axis_tready(rx_axis_tready),
        .m_axis_tdata(buf_axis_tdata),
        .m_axis_tvalid(buf_axis_tvalid),
        .m_axis_tready(buf_axis_tready)
    );
    // assign buf_axis_tvalid = rx_axis_tvalid;
    // assign rx_axis_tready = buf_axis_tready;
    // assign buf_axis_tdata = rx_axis_tdata;

    axis_adapter #(
        .S_DATA_WIDTH(UART_WIDTH),
        .S_KEEP_ENABLE(0),
        .M_DATA_WIDTH(INP_WIDTH),
        .M_KEEP_ENABLE(0)
    )  rx_inp_adapter (
        .clk,
        .arstn,
        .s_axis_tdata(buf_axis_tdata),
        .s_axis_tvalid(buf_axis_tvalid),
        .s_axis_tready(buf_axis_tready),
        .m_axis_tdata(inp_axis_tdata),
        .m_axis_tvalid(inp_axis_tvalid),
        .m_axis_tready(inp_axis_tready)
    );

    axis_adapter #(
        .S_DATA_WIDTH(OUT_WIDTH),
        .S_KEEP_ENABLE(0),
        .M_DATA_WIDTH(UART_WIDTH),
        .M_KEEP_ENABLE(0)
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
