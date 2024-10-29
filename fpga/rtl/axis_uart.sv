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

typedef enum {
    IDLE = 0,
    START,
    DATA,
    STOP
} state_t;

// AXI4-Stream UART receiver
module uart_rx #(
    parameter real CLK_FREQ,
    parameter int BAUD_RATE,
    parameter int DATA_WIDTH = 8,
    parameter int MIN_OVERSAMPLE = 16
) (
    input  logic                    clk,
    input  logic                    arstn,

    // AXI output
    output logic [DATA_WIDTH-1:0]   m_axis_tdata,
    output logic                    m_axis_tvalid,
    input  logic                    m_axis_tready,

    // UART interface
    input  logic                    rxd,

    // Status
    output logic                    busy,
    output logic                    overrun_error,
    output logic                    frame_error
);
    // input metastability synchronization
    logic rxd_sync;
    // second half of double-flopping is provided by rxd_samples register

    always_ff @(posedge clk or negedge arstn) begin: set_rxd_sync
        if (arstn == 0) begin
            rxd_sync <= 1;
        end else begin
            rxd_sync <= rxd;
        end
    end

    localparam real CLK_PER_BAUD = CLK_FREQ / BAUD_RATE;
    localparam int CLK_PER_SAMPLE = `max(`floor(CLK_PER_BAUD / MIN_OVERSAMPLE), 1);
    localparam int SAMPLE_PER_BAUD = CLK_PER_BAUD / CLK_PER_SAMPLE;

    state_t state;
    logic [$clog2(CLK_PER_SAMPLE)-1:0] clk_count;
    logic [$clog2(SAMPLE_PER_BAUD)-1:0] samples_count;
    logic [$clog2(DATA_WIDTH)-1:0] bit_count;

    always_ff @(posedge clk or negedge arstn) begin : set_clk_count
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

    always_ff @(posedge clk or negedge arstn) begin : set_samples_count
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

    logic [SAMPLE_PER_BAUD-1:0] rxd_samples;

    always @(posedge clk or negedge arstn) begin : set_rxd_samples
        if (arstn == 0) begin
            rxd_samples <= {SAMPLE_PER_BAUD{1'b1}};
        end else if ((clk_count == 0) && (state != IDLE)) begin
            rxd_samples <= {rxd_samples[SAMPLE_PER_BAUD-2:0], rxd_sync};
        end
    end

    logic [$clog2(SAMPLE_PER_BAUD + 1)-1:0] sum;
    logic sample_vote;

    always_comb begin : calc_sample_vote
        sum = 0;
        // we don't use the first or last samples in consensus
        for (int i = 1; i < SAMPLE_PER_BAUD - 1; i = i + 1) begin
            sum = sum + rxd_samples[i];
        end
        sample_vote = sum > ((SAMPLE_PER_BAUD - 2) / 2);
    end

    logic [DATA_WIDTH-1:0] rxd_data;

    always @(posedge clk or negedge arstn) begin : state_machine
        if (arstn == 0) begin
            state <= IDLE;
            bit_count <= 0;
            rxd_data <= 0;
            overrun_error <= 0;
            frame_error <= 0;
        end else begin
            if (m_axis_tready && m_axis_tvalid)
                m_axis_tvalid <= 0;
            case (state)
                IDLE: begin
                    bit_count <= 0;
                    rxd_data <= 0;
                    overrun_error <= 0;
                    frame_error <= 0;
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
                    // check stop bit is high mid-sampling, then kick back to IDLE
                    if ((clk_count == 0) && (samples_count == (SAMPLE_PER_BAUD - 1) / 2)) begin
                        if (rxd_sync == 1) begin
                            m_axis_tdata <= rxd_data;
                            m_axis_tvalid <= 1;
                            frame_error <= 0;
                        end else begin
                            m_axis_tvalid <= 0;
                            frame_error <= 1;
                        end
                        overrun_error <= m_axis_tvalid;
                        state <= IDLE;
                    end
                end
                default: begin
                    state <= IDLE;
                end
            endcase
        end
    end

    assign busy = state != IDLE;

    // ila_0 (
    //     .clk(clk),
    //     .probe0(rxd),
    //     .probe1(rxd_sync),
    //     .probe2(state), // width 2
    //     .probe3(clk_count), // width 3
    //     .probe4(samples_count), // width 5
    //     .probe5(bit_count), // width 3
    //     .probe6(rxd_samples), // width 17
    //     .probe7(sample_vote),
    //     .probe8(rxd_data), // width 8
    //     .probe9(m_axis_tdata), // width 8
    //     .probe10(m_axis_tvalid),
    //     .probe11(m_axis_tready),
    //     .probe12(busy),
    //     .probe13(overrun_error),
    //     .probe14(frame_error)
    // );

endmodule

// AXI4-Stream UART transmitter
module uart_tx #(
    parameter real CLK_FREQ,
    parameter int BAUD_RATE,
    parameter int DATA_WIDTH = 8
) (
    input  logic                    clk,
    input  logic                    arstn,

    // AXI input
    input  logic [DATA_WIDTH-1:0]   s_axis_tdata,
    input  logic                    s_axis_tvalid,
    output logic                    s_axis_tready,

    // UART interface
    output logic                    txd,

    // Status
    output logic                    busy
);
    localparam real CLK_PER_BAUD = CLK_FREQ / BAUD_RATE;

    initial begin
        if (CLK_PER_BAUD < 1) begin
            $display("Error: baud rate too high for clock frequency");
            $finish;
        end
    end

    state_t state;

    localparam int CLK_MAX = (DATA_WIDTH + 2) * CLK_PER_BAUD;
    logic [$clog2(CLK_MAX)-1:0] clk_count, CLK_TARGETS[(DATA_WIDTH + 2)-1:0];

    genvar i;
    generate
        for (i = 0; i < DATA_WIDTH + 2; i = i + 1) begin: baud
            assign CLK_TARGETS[i] = (i + 1) * CLK_PER_BAUD;
        end
    endgenerate

    always @(posedge clk or negedge arstn) begin : set_clk_count
        if (arstn == 0) begin
            clk_count <= 0;
        end else begin
            if ((state != IDLE) && (clk_count < CLK_MAX)) begin
                clk_count <= clk_count + 1;
            end else begin
                clk_count <= 0;
            end
        end
    end

    logic [$clog2(DATA_WIDTH)-1:0] bit_count;
    logic [DATA_WIDTH-1:0] tdata;

    always @(posedge clk or negedge arstn) begin : state_machine
        if (arstn == 0) begin
            state <= IDLE;
            s_axis_tready <= 1;
            txd <= 1;
        end else begin
            case (state)
                IDLE: begin
                    if (s_axis_tvalid) begin
                        state <= START;
                        s_axis_tready <= 0;
                        txd <= 0;
                        tdata <= s_axis_tdata;
                    end
                end
                START: begin
                    if (clk_count == CLK_TARGETS[0] - 1) begin
                        state <= DATA;
                        bit_count <= 0;
                        txd <= tdata[0];
                    end
                end
                DATA: begin
                    if (clk_count == CLK_TARGETS[(bit_count + 1)] - 1) begin
                        if (bit_count == DATA_WIDTH - 1) begin
                            state <= STOP;
                            txd <= 1;
                        end else begin
                            txd <= tdata[bit_count + 1];
                        end
                        bit_count <= bit_count + 1;
                    end
                end
                STOP: begin
                    if (clk_count == CLK_MAX - 1) begin
                        state <= IDLE;
                        s_axis_tready <= 1;
                    end
                end
                default: begin
                    state <= IDLE;
                    s_axis_tready <= 1;
                    txd <= 1;
                end
            endcase
        end
    end

    assign busy = state != IDLE;

endmodule

// AXI4-Stream UART transceiver
module uart #(
    parameter real CLK_FREQ,
    parameter int BAUD_RATE,
    parameter int DATA_WIDTH = 8
) (
    input  logic                    clk,
    input  logic                    arstn,

    // AXI input
    input  logic [DATA_WIDTH-1:0]   s_axis_tdata,
    input  logic                    s_axis_tvalid,
    output logic                    s_axis_tready,

    // AXI output
    output logic [DATA_WIDTH-1:0]   m_axis_tdata,
    output logic                    m_axis_tvalid,
    input  logic                    m_axis_tready,

    // UART interface
    input  logic                    rxd,
    output logic                    txd,

    // Status
    output logic                    tx_busy,
    output logic                    rx_busy,
    output logic                    rx_overrun_error,
    output logic                    rx_frame_error
);

    uart_tx #(
        .CLK_FREQ(CLK_FREQ),
        .BAUD_RATE(BAUD_RATE),
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
        .busy(tx_busy)
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
