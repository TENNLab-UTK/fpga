#************************************************************
# THIS IS A WIZARD-GENERATED FILE.                           
#
# Version 13.0.1 Build 232 06/12/2013 Service Pack 1 SJ Full Version
#
#************************************************************

# Copyright (C) 1991-2013 Altera Corporation
# Your use of Altera Corporation's design tools, logic functions 
# and other software and tools, and its AMPP partner logic 
# functions, and any output files from any of the foregoing 
# (including device programming or simulation files), and any 
# associated documentation or information are expressly subject 
# to the terms and conditions of the Altera Program License 
# Subscription Agreement, Altera MegaCore Function License 
# Agreement, or other applicable license agreement, including, 
# without limitation, that your use is for the sole purpose of 
# programming logic devices manufactured by Altera and sold by 
# Altera or its authorized distributors.  Please refer to the 
# applicable agreement for further details.



# Clock constraints

create_clock -name "clock_50_2" -period 20.000ns [get_ports {CLOCK_50_B5B}]
create_clock -name "clock_50_3" -period 20.000ns [get_ports {CLOCK_50_B6A}]
create_clock -name "clock_50_4" -period 20.000ns [get_ports {CLOCK_50_B7A}]
create_clock -name "clock_50_5" -period 20.000ns [get_ports {CLOCK_50_B8A}]

## Override the default 10 MHz JTAG TCK:
#create_clock -name altera_reserved_tck -period 30.00  -waveform {0.000 15.0} {altera_reserved_tck}
#set_input_delay -clock altera_reserved_tck 8 [get_ports altera_reserved_tdi]
#set_input_delay -clock altera_reserved_tck 8 [get_ports altera_reserved_tms]
#set_output_delay -clock altera_reserved_tck -clock_fall  -fall -max 10 [get_ports altera_reserved_tdo]
#set_output_delay -clock altera_reserved_tck -clock_fall  -rise -max 10 [get_ports altera_reserved_tdo]
#set_output_delay -clock altera_reserved_tck -clock_fall  -fall -min .2 [get_ports altera_reserved_tdo]
#set_output_delay -clock altera_reserved_tck -clock_fall  -rise -min .2 [get_ports altera_reserved_tdo]


# Automatically constrain PLL and other generated clocks
derive_pll_clocks -create_base_clocks

# Automatically calculate clock uncertainty to jitter and other effects.
derive_clock_uncertainty

# tsu/th constraints

# tco constraints

# tpd constraints

