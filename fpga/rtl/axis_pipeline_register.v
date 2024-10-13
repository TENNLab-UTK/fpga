// Copyright (c) 2018 Alex Forencich
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
 * AXI4-Stream pipeline register
 */
module axis_pipeline_register #
(
    // Width of AXI stream interfaces in bits
    parameter DATA_WIDTH = 8,
    // Propagate tkeep signal
    parameter KEEP_ENABLE = (DATA_WIDTH>8),
    // Propagate tid signal
    parameter ID_ENABLE = 0,
    // tid signal width
    parameter ID_WIDTH = 8,
    // Propagate tdest signal
    parameter DEST_ENABLE = 0,
    // tdest signal width
    parameter DEST_WIDTH = 8,
    // Propagate tuser signal
    parameter USER_ENABLE = 1,
    // tuser signal width
    parameter USER_WIDTH = 1,
    // Register type
    // 0 to bypass, 1 for simple buffer, 2 for skid buffer
    parameter REG_TYPE = 2,
    // Number of registers in pipeline
    parameter LENGTH = 2
)
(
    input  wire                             clk,
    input  wire                             rst,

    /*
     * AXI input
     */
    input  wire [DATA_WIDTH-1:0]            s_axis_tdata,
    input  wire [((DATA_WIDTH+7)/8)-1:0]    s_axis_tkeep,
    input  wire                             s_axis_tvalid,
    output wire                             s_axis_tready,
    input  wire                             s_axis_tlast,
    input  wire [ID_WIDTH-1:0]              s_axis_tid,
    input  wire [DEST_WIDTH-1:0]            s_axis_tdest,
    input  wire [USER_WIDTH-1:0]            s_axis_tuser,

    /*
     * AXI output
     */
    output wire [DATA_WIDTH-1:0]            m_axis_tdata,
    output wire [((DATA_WIDTH+7)/8)-1:0]    m_axis_tkeep,
    output wire                             m_axis_tvalid,
    input  wire                             m_axis_tready,
    output wire                             m_axis_tlast,
    output wire [ID_WIDTH-1:0]              m_axis_tid,
    output wire [DEST_WIDTH-1:0]            m_axis_tdest,
    output wire [USER_WIDTH-1:0]            m_axis_tuser
);
    localparam KEEP_WIDTH = (DATA_WIDTH + 7) / 8;

    wire [DATA_WIDTH-1:0]  axis_tdata[0:LENGTH];
    wire [KEEP_WIDTH-1:0]  axis_tkeep[0:LENGTH];
    wire                   axis_tvalid[0:LENGTH];
    wire                   axis_tready[0:LENGTH];
    wire                   axis_tlast[0:LENGTH];
    wire [ID_WIDTH-1:0]    axis_tid[0:LENGTH];
    wire [DEST_WIDTH-1:0]  axis_tdest[0:LENGTH];
    wire [USER_WIDTH-1:0]  axis_tuser[0:LENGTH];

    assign axis_tdata[0] = s_axis_tdata;
    assign axis_tkeep[0] = s_axis_tkeep;
    assign axis_tvalid[0] = s_axis_tvalid;
    assign s_axis_tready = axis_tready[0];
    assign axis_tlast[0] = s_axis_tlast;
    assign axis_tid[0] = s_axis_tid;
    assign axis_tdest[0] = s_axis_tdest;
    assign axis_tuser[0] = s_axis_tuser;

    assign m_axis_tdata = axis_tdata[LENGTH];
    assign m_axis_tkeep = axis_tkeep[LENGTH];
    assign m_axis_tvalid = axis_tvalid[LENGTH];
    assign axis_tready[LENGTH] = m_axis_tready;
    assign m_axis_tlast = axis_tlast[LENGTH];
    assign m_axis_tid = axis_tid[LENGTH];
    assign m_axis_tdest = axis_tdest[LENGTH];
    assign m_axis_tuser = axis_tuser[LENGTH];

    generate
        genvar i;

        for (i = 0; i < LENGTH; i = i + 1) begin : pipe_reg
            axis_register #(
                .DATA_WIDTH,
                .KEEP_ENABLE,
                .KEEP_WIDTH,
                .LAST_ENABLE,
                .ID_ENABLE,
                .ID_WIDTH,
                .DEST_ENABLE,
                .DEST_WIDTH,
                .USER_ENABLE,
                .USER_WIDTH,
                .REG_TYPE
            )
            reg_inst (
                .clk(clk),
                .rst(rst),
                // AXI input
                .s_axis_tdata(axis_tdata[i]),
                .s_axis_tkeep(axis_tkeep[i]),
                .s_axis_tvalid(axis_tvalid[i]),
                .s_axis_tready(axis_tready[i]),
                .s_axis_tlast(axis_tlast[i]),
                .s_axis_tid(axis_tid[i]),
                .s_axis_tdest(axis_tdest[i]),
                .s_axis_tuser(axis_tuser[i]),
                // AXI output
                .m_axis_tdata(axis_tdata[i+1]),
                .m_axis_tkeep(axis_tkeep[i+1]),
                .m_axis_tvalid(axis_tvalid[i+1]),
                .m_axis_tready(axis_tready[i+1]),
                .m_axis_tlast(axis_tlast[i+1]),
                .m_axis_tid(axis_tid[i+1]),
                .m_axis_tdest(axis_tdest[i+1]),
                .m_axis_tuser(axis_tuser[i+1])
            );
        end
    endgenerate
endmodule
