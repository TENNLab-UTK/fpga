`timescale 1ns/1ps

import processor_tlast_config::*;

module dma_simple_axis_tb;

    // Global signals
    logic clk;
    logic arstn;

    // AXIS master signals
    logic m_tvalid;
    logic m_tready;
    logic [(OUT_TDATA_WIDTH_BYTES * 8 - 1):0] m_tdata;
    logic [OUT_TDATA_WIDTH_BYTES-1:0] m_tkeep;
    logic m_tlast;
    
    // AXIS slave signals
    logic s_tvalid;
    logic s_tready;
    logic [(INP_TDATA_WIDTH_BYTES * 8 - 1):0] s_tdata;
    logic [INP_TDATA_WIDTH_BYTES-1:0] s_tkeep;
    logic s_tlast;

    // axis_processor_top uut (
    //     .clk(clk),
    //     .arstn(arstn),
    //     .m_tvalid(m_tvalid),
    //     .m_tready(m_tready),
    //     .m_tdata(m_tdata),
    //     .m_tkeep(m_tkeep),
    //     .m_tlast(m_tlast),
    //     .s_tvalid(s_tvalid),
    //     .s_tready(s_tready),
    //     .s_tdata(s_tdata),
    //     .s_tkeep(s_tkeep),
    //     .s_tlast(s_tlast)
    // );

    axis #(.DATA_WIDTH_BYTES(INP_TDATA_WIDTH_BYTES)) s_axis();
    axis #(.DATA_WIDTH_BYTES(OUT_TDATA_WIDTH_BYTES)) m_axis();

    assign s_axis.tvalid = s_tvalid;
    assign s_tready = s_axis.tready;
    assign s_axis.tdata = s_tdata;
    assign s_axis.tkeep = s_tkeep;
    assign s_axis.tlast = s_tlast;
    assign m_tvalid = m_axis.tvalid;
    assign m_axis.tready = m_tready;
    assign m_tdata = m_axis.tdata;
    assign m_tkeep = m_axis.tkeep;
    assign m_tlast = m_axis.tlast;

    axis_processor_tlast uut (
        .clk(clk),
        .arstn(arstn),
        .s_axis(s_axis),
        .m_axis(m_axis)
    );

    // Simulate simple network's input data packet using AXI Stream
    initial begin: axis_sim
        
        m_tready = 0;
        s_tvalid = 0;
        s_tdata = 0;
        s_tkeep = 0;
        s_tlast = 0;

        // Wait for reset
        #35;

        // Assign m_tready to high for the whole simulation
        m_tready = 1;
        #5;

        @(posedge clk);

        // Set valid input data packet and wait until a clock rising edge where s_tready is high (indicates successful AXIS handshake)
        s_tdata = 8'h08;
        s_tkeep = 4'b1111;
        s_tvalid = 1;
        @(posedge clk);
        while(s_tready != 1) begin
            @(posedge clk);
        end

        s_tdata = 8'h20;
        @(posedge clk);
        while(s_tready != 1) begin
            @(posedge clk);
        end

        // Last piece of data, so set tlast
        s_tdata = 8'h28;
        s_tlast = 1;
        @(posedge clk);
        while(s_tready != 1) begin
            @(posedge clk);
        end

        // End of final transfer
        s_tlast = 0;
        s_tvalid = 0;

        #30;

    end

    // Simulate 100MHz clock
    initial begin: clk_sim
        clk = 0;
        forever #5 clk = ~clk;
    end

    // Simulate reset signal
    initial begin: rst_sim
        arstn = 1;
        #7;
        arstn = 0;
        #18;
        arstn = 1;
    end

endmodule: dma_simple_axis_tb;