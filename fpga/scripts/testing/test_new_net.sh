#!/bin/bash

# Unload FPGA-related modules from kernel
dma_module_path=$(find /lib/modules/$unamer -type f -name 'dmaproxy.ko')
rmmod $dma_module_path

# Program FPGA
fpgautil -b /home/petalinux/network.bit.bin

# Re-load FPGA-related modules into kernel
insmod $dma_module_path

cd /home/petalinux/zynq_framework/cpp-apps
time bin/processor_tool_zynq_dma < /home/petalinux/proc_tool_commands_zynq.txt > /home/petalinux/proc_tool_output_fires_fpga.txt

time bin/processor_tool_risp < /home/petalinux/proc_tool_commands_zynq.txt > /home/petalinux/proc_tool_output_fires_sim_zynq.txt

cd /home/petalinux
diff -s proc_tool_output_fires_sim.txt proc_tool_output_fires_fpga.txt | tail -n 1

echo NETWORK HARDWARE TEST COMPLETE
