import subprocess

with open(".tmp.tcl", 'w') as tcl_f:
    tcl_f.write('''set argv [list "--inp_pkt_width_bits" "8" "--out_pkt_width_bits" "8"]\nset argc [llength $argv]\nset argv0 [file join [file dirname [info script]] pynq_dma.tcl]\nsource $argv0\n''')

bash_cmd = "vivado -mode batch -source .tmp.tcl"

result = subprocess.run(bash_cmd.split(' '))

print(result.returncode)