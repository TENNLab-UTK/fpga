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

/*
 * AXI4-Stream UART receiver
 */
module uart_rx #(
    parameter DATA_WIDTH = 8
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
    output wire                   frame_error,

    /*
     * Configuration
     */
    input  wire [15:0]            prescale
);
    reg [DATA_WIDTH-1:0] m_axis_tdata_reg = 0;
    reg m_axis_tvalid_reg = 0;

    reg rxd_reg = 1;

    reg busy_reg = 0;
    reg overrun_error_reg = 0;
    reg frame_error_reg = 0;

    reg [DATA_WIDTH-1:0] data_reg = 0;
    reg [18:0] prescale_reg = 0;
    reg [3:0] bit_cnt = 0;

    assign m_axis_tdata = m_axis_tdata_reg;
    assign m_axis_tvalid = m_axis_tvalid_reg;

    assign busy = busy_reg;
    assign overrun_error = overrun_error_reg;
    assign frame_error = frame_error_reg;

    always @(posedge clk or negedge arstn) begin
        if (arstn == 0) begin
            m_axis_tdata_reg <= 0;
            m_axis_tvalid_reg <= 0;
            rxd_reg <= 1;
            prescale_reg <= 0;
            bit_cnt <= 0;
            busy_reg <= 0;
            overrun_error_reg <= 0;
            frame_error_reg <= 0;
        end else begin
            rxd_reg <= rxd;
            overrun_error_reg <= 0;
            frame_error_reg <= 0;

            if (m_axis_tvalid && m_axis_tready) begin
                m_axis_tvalid_reg <= 0;
            end

            if (prescale_reg > 0) begin
                prescale_reg <= prescale_reg - 1;
            end else if (bit_cnt > 0) begin
                if (bit_cnt > DATA_WIDTH+1) begin
                    if (!rxd_reg) begin
                        bit_cnt <= bit_cnt - 1;
                        prescale_reg <= (prescale << 3)-1;
                    end else begin
                        bit_cnt <= 0;
                        prescale_reg <= 0;
                    end
                end else if (bit_cnt > 1) begin
                    bit_cnt <= bit_cnt - 1;
                    prescale_reg <= (prescale << 3)-1;
                    data_reg <= {rxd_reg, data_reg[DATA_WIDTH-1:1]};
                end else if (bit_cnt == 1) begin
                    bit_cnt <= bit_cnt - 1;
                    if (rxd_reg) begin
                        m_axis_tdata_reg <= data_reg;
                        m_axis_tvalid_reg <= 1;
                        overrun_error_reg <= m_axis_tvalid_reg;
                    end else begin
                        frame_error_reg <= 1;
                    end
                end
            end else begin
                busy_reg <= 0;
                if (!rxd_reg) begin
                    prescale_reg <= (prescale << 2)-2;
                    bit_cnt <= DATA_WIDTH+2;
                    data_reg <= 0;
                    busy_reg <= 1;
                end
            end
        end
    end
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
    output wire                   rx_frame_error,

    /*
     * Configuration
     */
    input  wire [15:0]            prescale
);
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
        .frame_error(rx_frame_error),
        // configuration
        .prescale(prescale)
    );
endmodule
