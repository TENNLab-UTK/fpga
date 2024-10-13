// Copyright (c) 2014-2018 Alex Forencich
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
 * AXI4-Stream register
 */
module axis_register #
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
    parameter REG_TYPE = 2
)
(
    input  wire                             clk,
    input  wire                             arstn,

    /*
     * AXI Stream input
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
     * AXI Stream output
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

    generate
        if (REG_TYPE > 1) begin
            // skid buffer, no bubble cycles

            // datapath registers
            reg                  s_axis_tready_reg = 1'b0;

            reg [DATA_WIDTH-1:0] m_axis_tdata_reg  = {DATA_WIDTH{1'b0}};
            reg [KEEP_WIDTH-1:0] m_axis_tkeep_reg  = {KEEP_WIDTH{1'b0}};
            reg                  m_axis_tvalid_reg = 1'b0, m_axis_tvalid_next;
            reg                  m_axis_tlast_reg  = 1'b0;
            reg [ID_WIDTH-1:0]   m_axis_tid_reg    = {ID_WIDTH{1'b0}};
            reg [DEST_WIDTH-1:0] m_axis_tdest_reg  = {DEST_WIDTH{1'b0}};
            reg [USER_WIDTH-1:0] m_axis_tuser_reg  = {USER_WIDTH{1'b0}};

            reg [DATA_WIDTH-1:0] temp_m_axis_tdata_reg  = {DATA_WIDTH{1'b0}};
            reg [KEEP_WIDTH-1:0] temp_m_axis_tkeep_reg  = {KEEP_WIDTH{1'b0}};
            reg                  temp_m_axis_tvalid_reg = 1'b0, temp_m_axis_tvalid_next;
            reg                  temp_m_axis_tlast_reg  = 1'b0;
            reg [ID_WIDTH-1:0]   temp_m_axis_tid_reg    = {ID_WIDTH{1'b0}};
            reg [DEST_WIDTH-1:0] temp_m_axis_tdest_reg  = {DEST_WIDTH{1'b0}};
            reg [USER_WIDTH-1:0] temp_m_axis_tuser_reg  = {USER_WIDTH{1'b0}};

            // datapath control
            reg store_axis_input_to_output;
            reg store_axis_input_to_temp;
            reg store_axis_temp_to_output;

            assign s_axis_tready = s_axis_tready_reg;
            assign m_axis_tdata  = m_axis_tdata_reg;
            assign m_axis_tkeep  = KEEP_ENABLE ? m_axis_tkeep_reg : {KEEP_WIDTH{1'b1}};
            assign m_axis_tvalid = m_axis_tvalid_reg;
            assign m_axis_tlast  = m_axis_tlast_reg;
            assign m_axis_tid    = ID_ENABLE   ? m_axis_tid_reg   : {ID_WIDTH{1'b0}};
            assign m_axis_tdest  = DEST_ENABLE ? m_axis_tdest_reg : {DEST_WIDTH{1'b0}};
            assign m_axis_tuser  = USER_ENABLE ? m_axis_tuser_reg : {USER_WIDTH{1'b0}};

            // enable ready input next cycle if output is ready or the temp reg will not be filled on the next cycle (output reg empty or no input)
            wire s_axis_tready_early = m_axis_tready || (!temp_m_axis_tvalid_reg && (!m_axis_tvalid_reg || !s_axis_tvalid));

            always @* begin
                // transfer sink ready state to source
                m_axis_tvalid_next = m_axis_tvalid_reg;
                temp_m_axis_tvalid_next = temp_m_axis_tvalid_reg;

                store_axis_input_to_output = 1'b0;
                store_axis_input_to_temp = 1'b0;
                store_axis_temp_to_output = 1'b0;

                if (s_axis_tready_reg) begin
                    // input is ready
                    if (m_axis_tready || !m_axis_tvalid_reg) begin
                        // output is ready or currently not valid, transfer data to output
                        m_axis_tvalid_next = s_axis_tvalid;
                        store_axis_input_to_output = 1'b1;
                    end else begin
                        // output is not ready, store input in temp
                        temp_m_axis_tvalid_next = s_axis_tvalid;
                        store_axis_input_to_temp = 1'b1;
                    end
                end else if (m_axis_tready) begin
                    // input is not ready, but output is ready
                    m_axis_tvalid_next = temp_m_axis_tvalid_reg;
                    temp_m_axis_tvalid_next = 1'b0;
                    store_axis_temp_to_output = 1'b1;
                end
            end

            always @(posedge clk or negedge arstn) begin
                if (arstn == 0) begin
                    s_axis_tready_reg <= 1'b0;
                    m_axis_tvalid_reg <= 1'b0;
                    temp_m_axis_tvalid_reg <= 1'b0;
                end else begin
                    s_axis_tready_reg <= s_axis_tready_early;
                    m_axis_tvalid_reg <= m_axis_tvalid_next;
                    temp_m_axis_tvalid_reg <= temp_m_axis_tvalid_next;

                    // datapath
                    if (store_axis_input_to_output) begin
                        m_axis_tdata_reg <= s_axis_tdata;
                        m_axis_tkeep_reg <= s_axis_tkeep;
                        m_axis_tlast_reg <= s_axis_tlast;
                        m_axis_tid_reg   <= s_axis_tid;
                        m_axis_tdest_reg <= s_axis_tdest;
                        m_axis_tuser_reg <= s_axis_tuser;
                    end else if (store_axis_temp_to_output) begin
                        m_axis_tdata_reg <= temp_m_axis_tdata_reg;
                        m_axis_tkeep_reg <= temp_m_axis_tkeep_reg;
                        m_axis_tlast_reg <= temp_m_axis_tlast_reg;
                        m_axis_tid_reg   <= temp_m_axis_tid_reg;
                        m_axis_tdest_reg <= temp_m_axis_tdest_reg;
                        m_axis_tuser_reg <= temp_m_axis_tuser_reg;
                    end

                    if (store_axis_input_to_temp) begin
                        temp_m_axis_tdata_reg <= s_axis_tdata;
                        temp_m_axis_tkeep_reg <= s_axis_tkeep;
                        temp_m_axis_tlast_reg <= s_axis_tlast;
                        temp_m_axis_tid_reg   <= s_axis_tid;
                        temp_m_axis_tdest_reg <= s_axis_tdest;
                        temp_m_axis_tuser_reg <= s_axis_tuser;
                    end
                end
            end

        end else if (REG_TYPE == 1) begin
            // simple register, inserts bubble cycles

            // datapath registers
            reg                  s_axis_tready_reg = 1'b0;
            reg [DATA_WIDTH-1:0] m_axis_tdata_reg  = {DATA_WIDTH{1'b0}};
            reg [KEEP_WIDTH-1:0] m_axis_tkeep_reg  = {KEEP_WIDTH{1'b0}};
            reg                  m_axis_tvalid_reg = 1'b0, m_axis_tvalid_next;
            reg                  m_axis_tlast_reg  = 1'b0;
            reg [ID_WIDTH-1:0]   m_axis_tid_reg    = {ID_WIDTH{1'b0}};
            reg [DEST_WIDTH-1:0] m_axis_tdest_reg  = {DEST_WIDTH{1'b0}};
            reg [USER_WIDTH-1:0] m_axis_tuser_reg  = {USER_WIDTH{1'b0}};

            // datapath control
            reg store_axis_input_to_output;

            assign s_axis_tready = s_axis_tready_reg;
            assign m_axis_tdata  = m_axis_tdata_reg;
            assign m_axis_tkeep  = KEEP_ENABLE ? m_axis_tkeep_reg : {KEEP_WIDTH{1'b1}};
            assign m_axis_tvalid = m_axis_tvalid_reg;
            assign m_axis_tlast  = m_axis_tlast_reg;
            assign m_axis_tid    = ID_ENABLE   ? m_axis_tid_reg   : {ID_WIDTH{1'b0}};
            assign m_axis_tdest  = DEST_ENABLE ? m_axis_tdest_reg : {DEST_WIDTH{1'b0}};
            assign m_axis_tuser  = USER_ENABLE ? m_axis_tuser_reg : {USER_WIDTH{1'b0}};

            // enable ready input next cycle if output buffer will be empty
            wire s_axis_tready_early = !m_axis_tvalid_next;

            always @* begin
                // transfer sink ready state to source
                m_axis_tvalid_next = m_axis_tvalid_reg;
                store_axis_input_to_output = 1'b0;

                if (s_axis_tready_reg) begin
                    m_axis_tvalid_next = s_axis_tvalid;
                    store_axis_input_to_output = 1'b1;
                end else if (m_axis_tready) begin
                    m_axis_tvalid_next = 1'b0;
                end
            end

            always @(posedge clk or negedge arstn) begin
                if (arstn == 0) begin
                    s_axis_tready_reg <= 1'b0;
                    m_axis_tvalid_reg <= 1'b0;
                end else begin
                    s_axis_tready_reg <= s_axis_tready_early;
                    m_axis_tvalid_reg <= m_axis_tvalid_next;
                    // datapath
                    if (store_axis_input_to_output) begin
                        m_axis_tdata_reg <= s_axis_tdata;
                        m_axis_tkeep_reg <= s_axis_tkeep;
                        m_axis_tlast_reg <= s_axis_tlast;
                        m_axis_tid_reg   <= s_axis_tid;
                        m_axis_tdest_reg <= s_axis_tdest;
                        m_axis_tuser_reg <= s_axis_tuser;
                    end
                end
            end
        end else begin
            // bypass
            assign m_axis_tdata  = s_axis_tdata;
            assign m_axis_tkeep  = KEEP_ENABLE ? s_axis_tkeep : {KEEP_WIDTH{1'b1}};
            assign m_axis_tvalid = s_axis_tvalid;
            assign m_axis_tlast  = s_axis_tlast;
            assign m_axis_tid    = ID_ENABLE   ? s_axis_tid   : {ID_WIDTH{1'b0}};
            assign m_axis_tdest  = DEST_ENABLE ? s_axis_tdest : {DEST_WIDTH{1'b0}};
            assign m_axis_tuser  = USER_ENABLE ? s_axis_tuser : {USER_WIDTH{1'b0}};
            assign s_axis_tready = m_axis_tready;
        end
    endgenerate
endmodule