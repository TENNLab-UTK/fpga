import neuro
import subprocess
import pathlib as pl
from fpga.network import build_network_sv, charge_width
from fpga._math import clog2, width_bits_to_bytes, width_bytes_to_bits, width_nearest_byte

def width_nearest_pow2_bits(w) -> int:
    return width_bytes_to_bits(1 << clog2(width_bits_to_bytes(w)))

def build_network_sv_from_file(net_path: str = "", net_sv_path: str = "") -> neuro.Network:
    net_fpath = pl.Path(net_path)
    if not net_fpath.is_file():
        raise RuntimeError("build_network_sv_from_file() - The given network path, " + str(net_path) + ", is not a valid file path.")

    net = neuro.Network()
    net.read_from_file(net_path)

    build_network_sv(net, net_sv_path)

    return net

def gen_bitstream(net_sv_path: str = "", vivado_dir_path: str = "", inp_width_bits: int = 16, out_width_bits: int = 16) -> int:
    vivado_dir_fpath = pl.Path(vivado_dir_path)

    if not vivado_dir_fpath.is_dir():
        vivado_dir_fpath.mkdir(parents=True, exist_ok=True)

    this_script_fpath = pl.Path(__file__).resolve()
    if "pynq_dma_hw_gen.py" not in str(this_script_fpath):
        raise RuntimeError("gen_bitstream() - Could not resolve the file path for this Python script.")

    with open(str(vivado_dir_fpath.parent) + "/gen_bitstream.tcl", 'w') as tcl_f:
        tcl_f.write('''set argv [list "--net_sv_path" "''' + net_sv_path + '''" "--project_dir" "''' + vivado_dir_path + '''" "--inp_pkt_width_bits" "''' + str(inp_width_bits) + '''" "--out_pkt_width_bits" "''' + str(out_width_bits) + '''"]\nset argc [llength $argv]\nset argv0 [file join [file dirname [info script]] ''' + str(this_script_fpath.parent) + '''/../pynq_dma.tcl]\nsource $argv0\n''')

    bash_cmd = "vivado -mode batch -source " + str(vivado_dir_fpath.parent) + "/gen_bitstream.tcl"

    result = subprocess.run(bash_cmd.split(' '), cwd=vivado_dir_path)

    return result.returncode

def process_network(net_path: str = "", vivado_dir_path: str = "") -> int:
    this_script_fpath = pl.Path(__file__).resolve()
    if "pynq_dma_hw_gen.py" not in str(this_script_fpath):
        raise RuntimeError("process_network() - Could not resolve the file path for this Python script.")
    
    vivado_dir_fpath = pl.Path(vivado_dir_path)
    if not vivado_dir_fpath.is_dir():
        vivado_dir_fpath.mkdir(parents=True, exist_ok=True)
    
    net_fpath = pl.Path(net_path)
    if not net_fpath.is_file():
        raise RuntimeError("process_network() - The given network path, " + str(net_path) + ", is not a valid file path.")

    net_sv_path = str(vivado_dir_fpath) + "/" + net_fpath.stem + ".sv"
    net = build_network_sv_from_file(net_path, net_sv_path)

    spk_width = net.num_inputs() * charge_width(net)
    run_width = width_nearest_byte(spk_width + 1) - 1
    src_width = 1 + max(spk_width, run_width)
    inp_width_bits = width_nearest_pow2_bits(src_width)
    out_width_bits = width_nearest_pow2_bits(net.num_outputs() + 1)

    result = gen_bitstream(net_sv_path, str(vivado_dir_fpath), inp_width_bits, out_width_bits)
    
    return result


if __name__=="__main__":

    this_script_fpath = pl.Path(__file__).resolve()
    if "pynq_dma_hw_gen.py" not in str(this_script_fpath):
        raise RuntimeError("main() - Could not resolve the file path for this Python script.")
    
    result = process_network(str(this_script_fpath.parent) + "/../../../networks/xor_noleak.txt", str(this_script_fpath.parent) + "/tmp_pynq_dma_hw_gen_test")

    if result == 0:
        print("Successful bitstream generation")
    else:
        print("Bitstream generation was unsuccessful")