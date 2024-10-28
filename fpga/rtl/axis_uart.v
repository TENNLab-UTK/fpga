// Copyright (c) 2014-2017 Alex Forencich
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

/*
 * AXI4-Stream UART receiver
 */
module uart_rx #(
    parameter real CLK_FREQ = 100_000_000.0,
    parameter integer BAUD_RATE = 115_200,
    parameter integer DATA_WIDTH = 8,
    parameter integer MIN_OVERSAMPLE = 16
) (
    input  wire                   clk,
    input  wire                   arstn,

    /*
     * AXI output
     */
    output wire [DATA_WIDTH-1:0]  m_axis_tdata,
    output wire                   m_axis_tvalid,
    input  wire                   m_axis_tready,

    /*
     * UART interface
     */
    input  wire                   rxd,

    /*
     * Status
     */
    output wire                   busy,
    output wire                   overrun_error,
    output wire                   frame_error
);
    // input metastability synchronization
    reg rxd_sync;
    // second half of double-flopping is provided by rxd_samples register

    always @(posedge clk or negedge arstn) begin: set_rxd_sync
        if (arstn == 0) begin
            rxd_sync <= 1;
        end else begin
            rxd_sync <= rxd;
        end
    end

    localparam real CLK_PER_BAUD = CLK_FREQ / BAUD_RATE;
    // HACK: floor division
    localparam integer CLK_PER_SAMPLE = CLK_PER_BAUD / MIN_OVERSAMPLE - 0.5;
    localparam integer SAMPLE_PER_BAUD = CLK_PER_BAUD / CLK_PER_SAMPLE;

    localparam [1:0]
        IDLE = 2'b00,
        START = 2'b01,
        DATA = 2'b10,
        STOP = 2'b11;

    reg [1:0] state;
    reg [$clog2(CLK_PER_SAMPLE + 1)-1:0] clk_count;
    reg [$clog2(SAMPLE_PER_BAUD + 1)-1:0] samples_count;
    reg [$clog2(DATA_WIDTH + 1)-1:0] bit_count;

    always @(posedge clk or negedge arstn) begin : set_clk_count
        if (arstn == 0) begin
            clk_count <= 0;
        end else begin
            if ((state != IDLE) && (clk_count < CLK_PER_SAMPLE - 1)) begin
                clk_count <= clk_count + 1;
            end else begin
                clk_count <= 0;
            end
        end
    end

    always @(posedge clk or negedge arstn) begin : set_samples_count
        if (arstn == 0) begin
            samples_count <= 0;
        end else if (clk_count == 0) begin
            if ((state != IDLE) && (samples_count < SAMPLE_PER_BAUD - 1)) begin
                samples_count <= samples_count + 1;
            end else begin
                samples_count <= 0;
            end
        end
    end

    reg [SAMPLE_PER_BAUD-1:0] rxd_samples;

    always @(posedge clk or negedge arstn) begin : set_rxd_samples
        if (arstn == 0) begin
            rxd_samples <= {SAMPLE_PER_BAUD{1'b1}};
        end else if ((clk_count == 0) && (state != IDLE)) begin
            rxd_samples <= {rxd_samples[SAMPLE_PER_BAUD-2:0], rxd_sync};
        end
    end

    wire sample_vote;
    integer sum;
    integer i;
    always @* begin : calc_sample_vote
        sum = 0;
        // we don't use the first or last samples in consensus
        for (i = 1; i < SAMPLE_PER_BAUD - 1; i = i + 1) begin
            sum = sum + rxd_samples[i];
        end
    end
    assign sample_vote = sum > ((SAMPLE_PER_BAUD - 2) / 2);

    reg [DATA_WIDTH-1:0] rxd_data, tdata;
    reg tvalid, overrun_error_reg, frame_error_reg;

    always @(posedge clk or negedge arstn) begin : state_machine
        if (arstn == 0) begin
            state <= IDLE;
            bit_count <= 0;
            rxd_data <= 0;
            overrun_error_reg <= 0;
            frame_error_reg <= 0;
        end else begin
            if (m_axis_tready && m_axis_tvalid)
                tvalid <= 0;
            case (state)
                IDLE: begin
                    bit_count <= 0;
                    rxd_data <= 0;
                    overrun_error_reg <= 0;
                    frame_error_reg <= 0;
                    if (rxd_sync == 0)
                        state <= START;
                end
                START: begin
                    if (clk_count == 0) begin
                        if (samples_count == 0) begin
                            // if the start bit does not stay low one sample, we kick back to IDLE
                            if (rxd_sync == 1)
                                state <= IDLE;
                        end else if (samples_count == SAMPLE_PER_BAUD - 1) begin
                            if (sample_vote == 0)
                                state <= DATA;
                            else
                                state <= IDLE;
                        end
                    end
                end
                DATA: begin
                    if ((clk_count == 0) && (samples_count == SAMPLE_PER_BAUD - 1)) begin
                        rxd_data[bit_count] <= sample_vote;
                        bit_count <= bit_count + 1;
                        if (bit_count == DATA_WIDTH - 1) begin
                            state <= STOP;
                        end
                    end
                end
                STOP: begin
                    if ((clk_count == 0) && (samples_count == SAMPLE_PER_BAUD - 1)) begin
                        if (sample_vote == 1) begin
                            tdata <= rxd_data;
                            tvalid <= 1;
                            frame_error_reg <= 0;
                        end else begin
                            tvalid <= 0;
                            frame_error_reg <= 1;
                        end
                        overrun_error_reg <= tvalid;
                        state <= IDLE;
                    end
                end
                default: begin
                    state <= IDLE;
                end
            endcase
        end
    end

    assign m_axis_tdata = tdata;
    assign m_axis_tvalid = tvalid;
    assign busy = state != IDLE;
    assign overrun_error = overrun_error_reg;
    assign frame_error = frame_error_reg;

endmodule

/*
 * AXI4-Stream UART transmitter
 */
module uart_tx #(
    parameter DATA_WIDTH = 8
) (
    input  wire                   clk,
    input  wire                   arstn,

    /*
     * AXI input
     */
    input  wire [DATA_WIDTH-1:0]  s_axis_tdata,
    input  wire                   s_axis_tvalid,
    output wire                   s_axis_tready,

    /*
     * UART interface
     */
    output wire                   txd,

    /*
     * Status
     */
    output wire                   busy,

    /*
     * Configuration
     */
    input  wire [15:0]            prescale
);
    reg s_axis_tready_reg = 0;

    reg txd_reg = 1;

    reg busy_reg = 0;

    reg [DATA_WIDTH:0] data_reg = 0;
    reg [18:0] prescale_reg = 0;
    reg [3:0] bit_cnt = 0;

    assign s_axis_tready = s_axis_tready_reg;
    assign txd = txd_reg;

    assign busy = busy_reg;

    always @(posedge clk or negedge arstn) begin
        if (arstn == 0) begin
            s_axis_tready_reg <= 0;
            txd_reg <= 1;
            prescale_reg <= 0;
            bit_cnt <= 0;
            busy_reg <= 0;
        end else begin
            if (prescale_reg > 0) begin
                s_axis_tready_reg <= 0;
                prescale_reg <= prescale_reg - 1;
            end else if (bit_cnt == 0) begin
                s_axis_tready_reg <= 1;
                busy_reg <= 0;

                if (s_axis_tvalid) begin
                    s_axis_tready_reg <= !s_axis_tready_reg;
                    prescale_reg <= (prescale << 3)-1;
                    bit_cnt <= DATA_WIDTH+1;
                    data_reg <= {1'b1, s_axis_tdata};
                    txd_reg <= 0;
                    busy_reg <= 1;
                end
            end else begin
                if (bit_cnt > 1) begin
                    bit_cnt <= bit_cnt - 1;
                    prescale_reg <= (prescale << 3)-1;
                    {data_reg, txd_reg} <= {1'b0, data_reg};
                end else if (bit_cnt == 1) begin
                    bit_cnt <= bit_cnt - 1;
                    prescale_reg <= (prescale << 3);
                    txd_reg <= 1;
                end
            end
        end
    end
endmodule

/*
 * AXI4-Stream UART transceiver
 */
module uart #(
    parameter real CLK_FREQ = 100_000_000.0,
    parameter integer BAUD_RATE = 115_200,
    parameter integer DATA_WIDTH = 8
) (
    input  wire                   clk,
    input  wire                   arstn,

    /*
     * AXI input
     */
    input  wire [DATA_WIDTH-1:0]  s_axis_tdata,
    input  wire                   s_axis_tvalid,
    output wire                   s_axis_tready,

    /*
     * AXI output
     */
    output wire [DATA_WIDTH-1:0]  m_axis_tdata,
    output wire                   m_axis_tvalid,
    input  wire                   m_axis_tready,

    /*
     * UART interface
     */
    input  wire                   rxd,
    output wire                   txd,

    /*
     * Status
     */
    output wire                   tx_busy,
    output wire                   rx_busy,
    output wire                   rx_overrun_error,
    output wire                   rx_frame_error
);
    localparam integer PRESCALE = CLK_FREQ / (DATA_WIDTH * BAUD_RATE) - 0.5;
    wire [15:0] prescale;
    assign prescale = PRESCALE;

    uart_tx #(
        .DATA_WIDTH(DATA_WIDTH)
    ) uart_tx_inst (
        .clk(clk),
        .arstn(arstn),
        // axi input
        .s_axis_tdata(s_axis_tdata),
        .s_axis_tvalid(s_axis_tvalid),
        .s_axis_tready(s_axis_tready),
        // output
        .txd(txd),
        // status
        .busy(tx_busy),
        // configuration
        .prescale(prescale)
    );

    uart_rx #(
        .CLK_FREQ(CLK_FREQ),
        .BAUD_RATE(BAUD_RATE),
        .DATA_WIDTH(DATA_WIDTH)
    ) uart_rx_inst (
        .clk(clk),
        .arstn(arstn),
        // axi output
        .m_axis_tdata(m_axis_tdata),
        .m_axis_tvalid(m_axis_tvalid),
        .m_axis_tready(m_axis_tready),
        // input
        .rxd(rxd),
        // status
        .busy(rx_busy),
        .overrun_error(rx_overrun_error),
        .frame_error(rx_frame_error)
    );
endmodule
