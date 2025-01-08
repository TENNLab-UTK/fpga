`timescale 1ns/1ps

//import processor_config::*;

module axis_processor_tb;

    // Simulation constants
    localparam NUM_INP = 8;

    // Simulation signals
    logic [8-1:0] inp_data [0:NUM_INP-1];
    int t = 0;

    // Global signals
    logic clk;
    logic arstn;

    // AXIS master signals
    logic m_tvalid;
    logic m_tready;
    logic [8-1:0] m_tdata;
    
    // AXIS slave signals
    logic s_tvalid;
    logic s_tready;
    logic [8-1:0] s_tdata;

    axis_processor uut (
        .clk(clk),
        .arstn(arstn),
        .s_axis_tdata(s_tdata),
        .s_axis_tvalid(s_tvalid),
        .s_axis_tready(s_tready),
        .m_axis_tdata(m_tdata),
        .m_axis_tvalid(m_tvalid),
        .m_axis_tready(m_tready)
    );

    // Simulate network's input data packets using AXI Stream
    initial begin: axis_inp_sim


        // Fill test input array with input pkts
        // inp_data[0] = 16'b0110000000000000; // CLR
        // inp_data[1] = 16'b0100010000000000; // AS 0 0 1
        // inp_data[2] = 16'b0010000000000011; // RUN 3
        // inp_data[3] = 16'b0101010000000000; // AS 1 0 1
        // inp_data[4] = 16'b0010000000000011; // RUN 3
        // inp_data[5] = 16'b0100010000000000; // AS 0 0 1
        // inp_data[6] = 16'b0101010000000000; // AS 1 0 1
        // inp_data[7] = 16'b0010000000000011; // RUN 3
        inp_data[0] = 8'b11000000; // CLR
        inp_data[1] = 8'b10001000; // AS 0 0 1
        inp_data[2] = 8'b01000011; // RUN 3
        inp_data[3] = 8'b10101000; // AS 1 0 1
        inp_data[4] = 8'b01000011; // RUN 3
        inp_data[5] = 8'b10001000; // AS 0 0 1
        inp_data[6] = 8'b10101000; // AS 1 0 1
        inp_data[7] = 8'b01000011; // RUN 3

        
        m_tready = 0;
        s_tvalid = 0;
        s_tdata = 0;

        // Wait for reset
        #350;

        // Assign m_tready to high for the whole simulation
        m_tready = 1;
        #50;

        @(posedge clk);
        
        // Set valid signal high to indicate valid input packets
        s_tvalid = 1;

        // Send all input data to unit under test; for each packet, wait until a clock rising edge where s_tready is high (indicates successful AXIS handshake)
        foreach (inp_data[i]) begin
            #1;
            s_tdata = inp_data[i];
            @(posedge clk);
            while(s_tready != 1) begin
                @(posedge clk);
            end
        end
        
        // Set valid signal low after all input packets have been processed/sent
        #1;
        s_tvalid = 0;
    end

    // Simulate simple network's output data packet using AXI Stream
    initial begin: axis_out_sim
        forever begin
            @(posedge clk);
            if(m_tready == 1 && m_tvalid == 1) begin
                $display("%d: 0b%0b", t, m_tdata);
                t = t + 1;
            end
        end
    end

    // Simulate 10MHz clock
    initial begin: clk_sim
        clk = 0;
        forever #50 clk = ~clk;
    end

    // Simulate reset signal
    initial begin: rst_sim
        arstn = 1;
        #70;
        arstn = 0;
        #180;
        arstn = 1;
    end

endmodule: axis_processor_tb;