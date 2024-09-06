import neuro
import subprocess
import json
import pathlib as pl
from fpga.network import build_network_sv, charge_width
from fpga._math import clog2, width_bits_to_bytes, width_bytes_to_bits, width_nearest_byte

def width_nearest_pow2_bits(w) -> int:
    return width_bytes_to_bits(1 << clog2(width_bits_to_bytes(w)))

def build_network_sv_from_file(net_path: str = "", net_sv_path: str = "") -> neuro.Network:
    net_fpath = pl.Path(net_path)
    if not net_fpath.is_file():
        raise RuntimeError("build_network_sv_from_file() - The given network path, " + str(net_fpath) + ", is not a valid file path.")

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

    with open(str(vivado_dir_fpath) + "/gen_bitstream.tcl", 'w') as tcl_f:
        tcl_f.write('''set argv [list "--net_sv_path" "''' + net_sv_path + '''" "--project_dir" "''' + vivado_dir_path + '''" "--inp_pkt_width_bits" "''' + str(inp_width_bits) + '''" "--out_pkt_width_bits" "''' + str(out_width_bits) + '''"]\nset argc [llength $argv]\nset argv0 [file join [file dirname [info script]] ''' + str(this_script_fpath.parent) + '''/../pynq_dma.tcl]\nsource $argv0\n''')

    bash_cmd = "vivado -mode batch -source " + str(vivado_dir_fpath) + "/gen_bitstream.tcl"

    result = subprocess.run(bash_cmd.split(' '), cwd=vivado_dir_path)

    return result.returncode

def gen_zynq_dma_net(net: neuro.Network, zynq_dma_net_path: str = "", inp_width_bits: int = 16) -> None:
    zynq_dma_net_fpath = pl.Path(zynq_dma_net_path)

    if (not str(zynq_dma_net_fpath).endswith(".json")) and (not str(zynq_dma_net_fpath).endswith(".txt")):
        raise RuntimeError("gen_zynq_dma_net() - The given network path, " + str(zynq_dma_net_fpath) + ", must be a .json or .txt file.")

    if not zynq_dma_net_fpath.parent.is_dir():
        zynq_dma_net_fpath.parent.mkdir(parents=True, exist_ok=True)

    zynq_dma_net_json = net.as_json()

    if ("Associated_Data" in zynq_dma_net_json) and ("proc_params" in zynq_dma_net_json["Associated_Data"]):
        zynq_dma_net_json["Associated_Data"]["proc_params"]["zynq_dma"] = {}

        net_charge_width = charge_width(net)
        zynq_dma_net_json["Associated_Data"]["proc_params"]["zynq_dma"]["inp_pkt_structure"] = []
        zynq_dma_net_json["Associated_Data"]["proc_params"]["zynq_dma"]["out_pkt_structure"] = []
        starting_bit = inp_width_bits - net_charge_width*net.num_inputs() - 1
        
        net.make_sorted_node_vector()
        for node in net.sorted_node_vector:
            if node.input_id > -1:
                zynq_dma_net_json["Associated_Data"]["proc_params"]["zynq_dma"]["inp_pkt_structure"].append({"id": node.id, "starting_bit": starting_bit, "num_bits": net_charge_width})
                starting_bit += net_charge_width

            if node.output_id > -1:
                zynq_dma_net_json["Associated_Data"]["proc_params"]["zynq_dma"]["out_pkt_structure"].append(node.id)
    
        if "other" in zynq_dma_net_json["Associated_Data"]:
            zynq_dma_net_json["Associated_Data"]["other"] = "zynq_dma"

        zynq_dma_net_json_str = json.dumps(zynq_dma_net_json, indent=2)
        with open(zynq_dma_net_path, 'w') as file:
            file.write(zynq_dma_net_json_str)

    #"zynq_dma": {
        #     "inp_pkt_structure": [{"id": 1, "starting_bit": 3, "num_bits": 2}, {"id": 0, "starting_bit": 5, "num_bits": 2}],
        #     "out_pkt_structure": [4]
        # }

def process_network(net_path: str = "", zynq_dma_net_path: str = "", vivado_dir_path: str = "") -> int:
    this_script_fpath = pl.Path(__file__).resolve()
    if "pynq_dma_hw_gen.py" not in str(this_script_fpath):
        raise RuntimeError("process_network() - Could not resolve the file path for this Python script.")
    
    vivado_dir_fpath = pl.Path(vivado_dir_path)
    if not vivado_dir_fpath.is_dir():
        vivado_dir_fpath.mkdir(parents=True, exist_ok=True)
    
    net_fpath = pl.Path(net_path)
    if not net_fpath.is_file():
        raise RuntimeError("process_network() - The given network path, " + str(net_fpath) + ", is not a valid file path.")

    net_sv_path = str(vivado_dir_fpath) + "/" + net_fpath.stem + ".sv"
    net = build_network_sv_from_file(net_path, net_sv_path)

    spk_width = net.num_inputs() * charge_width(net)
    run_width = width_nearest_byte(spk_width + 1) - 1
    src_width = 1 + max(spk_width, run_width)
    inp_width_bits = width_nearest_pow2_bits(src_width)
    out_width_bits = width_nearest_pow2_bits(net.num_outputs() + 1)

    gen_zynq_dma_net(net, zynq_dma_net_path, inp_width_bits)

    result = gen_bitstream(net_sv_path, str(vivado_dir_fpath), inp_width_bits, out_width_bits)
    
    return result


if __name__=="__main__":

    this_script_fpath = pl.Path(__file__).resolve()
    if "pynq_dma_hw_gen.py" not in str(this_script_fpath):
        raise RuntimeError("main() - Could not resolve the file path for this Python script.")
    
    result = process_network(str(this_script_fpath.parent) + "/../../../networks/xor_noleak.txt", str(this_script_fpath.parent) + "/../../../networks/xor_noleak_zynq_dma.txt", str(this_script_fpath.parent) + "/tmp_pynq_dma_hw_gen_test")

    if result == 0:
        print("Successful bitstream generation")
    else:
        print("Bitstream generation was unsuccessful")