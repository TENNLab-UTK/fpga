import neuro
import subprocess
import pathlib as pl
from fpga.network import build_network_sv

def build_network_sv_from_file(net_path: str = "", net_sv_path: str = "") -> None:
    net_fpath = pl.Path(net_path)

    if not net_fpath.is_file():
        raise RuntimeError("build_network_sv_from_file() - The given network path, " + str(net_path) + ", is not a valid file path.")

    net = neuro.Network()
    net.read_from_file(net_path)

    build_network_sv(net, net_sv_path)

def gen_bitstream(net_sv_path: str = "", vivado_dir_path: str = "", inp_width_bits: int = 16, out_width_bits: int = 16) -> int:
    vivado_dir_fpath = pl.Path(vivado_dir_path)

    if not vivado_dir_fpath.is_dir():
        vivado_dir_fpath.mkdir(parents=True, exist_ok=True)

    this_script_fpath = pl.Path(__file__).resolve()
    if "pynq_dma_testing.py" not in str(this_script_fpath):
        raise RuntimeError("gen_bitstream() - Could not resolve the file path for this Python script.")

    with open(str(vivado_dir_fpath.parent) + "/gen_bitstream.tcl", 'w') as tcl_f:
        tcl_f.write('''set argv [list "--net_sv_path" "''' + net_sv_path + '''" "--project_dir" "''' + vivado_dir_path + '''" "--inp_pkt_width_bits" "''' + str(inp_width_bits) + '''" "--out_pkt_width_bits" "''' + str(out_width_bits) + '''"]\nset argc [llength $argv]\nset argv0 [file join [file dirname [info script]] ''' + str(this_script_fpath.parent) + '''/../pynq_dma.tcl]\nsource $argv0\n''')

    bash_cmd = "vivado -mode batch -source " + str(vivado_dir_fpath.parent) + "/gen_bitstream.tcl"

    result = subprocess.run(bash_cmd.split(' '), cwd=vivado_dir_path)

    return result.returncode

if __name__=="__main__":

    this_script_fpath = pl.Path(__file__).resolve()
    if "pynq_dma_testing.py" not in str(this_script_fpath):
        raise RuntimeError("gen_bitstream() - Could not resolve the file path for this Python script.")
    
    tmp_dir_fpath = pl.Path(str(this_script_fpath.parent) + "/tmp_test")
    if not tmp_dir_fpath.is_dir():
        tmp_dir_fpath.mkdir(parents=True, exist_ok=True)
    
    net_sv_path = str(tmp_dir_fpath) + "/xor_noleak.sv"
    build_network_sv_from_file(str(this_script_fpath.parent) + "/../../../networks/xor_noleak.txt", net_sv_path)
    result = gen_bitstream(net_sv_path, str(tmp_dir_fpath), 8, 8)

    if result == 0:
        print("Successful bitstream generation")
    else:
        print("Bitstream generation was unsuccessful")