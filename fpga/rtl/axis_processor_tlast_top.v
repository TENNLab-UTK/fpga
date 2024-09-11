module axis_processor_tlast_top #(
    parameter integer INP_TDATA_WIDTH_BYTES = 4,
    parameter integer OUT_TDATA_WIDTH_BYTES = 4
) (

    // Global signals
    input clk,
    input arstn,

    // AXIS master signals
    output m_tvalid,
    input m_tready,
    output [(OUT_TDATA_WIDTH_BYTES * 8 - 1):0] m_tdata,
    output [OUT_TDATA_WIDTH_BYTES-1:0] m_tkeep,
    output m_tlast,
    
    // AXIS slave signals
    input s_tvalid,
    output s_tready,
    input [(INP_TDATA_WIDTH_BYTES * 8 - 1):0] s_tdata,
    input [INP_TDATA_WIDTH_BYTES-1:0] s_tkeep,
    input s_tlast
);

    axis_processor_tlast_v_sv_adapter axis_processor_tlast_v_sv_adapter_0 (
        .clk(clk),
        .arstn(arstn),
        .m_tvalid(m_tvalid),
        .m_tready(m_tready),
        .m_tdata(m_tdata),
        // .m_tstrb(),
        .m_tkeep(m_tkeep),
        .m_tlast(m_tlast),
        // .m_tid(),
        // .m_tdest(),
        // .m_tuser(),
        .s_tvalid(s_tvalid),
        .s_tready(s_tready),
        .s_tdata(s_tdata),
        // .s_tstrb(0),
        .s_tkeep(s_tkeep),
        .s_tlast(s_tlast)
        // .s_tid(0),
        // .s_tdest(0),
        // .s_tuser(0)
    );
endmodule