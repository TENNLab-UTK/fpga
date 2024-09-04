import pathlib as pl

from network_gen import generate_network
from input_gen import gen_inputs
from pynq_dma_hw_gen import process_network

FRAMEWORK_REL_PATH = "../../../../"
TEST_DIR_REL_PATH_BASE = "test_"
TEMPLATE_NET_REL_PATH = "empty_net_risp.json"

def test_pynq_dma(test_id, num_neurons, num_synapses, num_inputs, num_outputs, num_sim_times, sim_time):

    # Find path to this python file
    this_script_fpath = pl.Path(__file__).resolve()
    if "pynq_dma_outer_test.py" not in str(this_script_fpath):
        raise RuntimeError("main() - Could not resolve the file path for this Python script.")
    
    # Find path to framework
    framework_fpath = pl.Path(str(this_script_fpath.parent) + "/" + FRAMEWORK_REL_PATH) 

    # Find path to test directory and create it if necessary
    test_dir_fpath = pl.Path(str(this_script_fpath.parent) + "/" + TEST_DIR_REL_PATH_BASE + str(test_id))
    if not test_dir_fpath.is_dir():
        test_dir_fpath.mkdir(parents=True, exist_ok=True)

    # Generate random network that is written out to a file
    template_net_json_fpath = pl.Path(str(this_script_fpath.parent) + "/" + TEMPLATE_NET_REL_PATH)
    rand_net_json_fpath = pl.Path(str(test_dir_fpath) + "/net.json")
    generate_network(str(template_net_json_fpath), str(framework_fpath), num_neurons, num_synapses, test_id, num_inputs, num_outputs, str(rand_net_json_fpath))

    # Generate random network input in the form of processor tool commands that are written to a file
    proc_tool_commands_fpath = pl.Path(str(test_dir_fpath) + "/proc_tool_commands.txt")
    proc_tool_output_fires_fpath = pl.Path(str(test_dir_fpath) + "/proc_tool_output_fires.txt")
    gen_inputs(str(rand_net_json_fpath), str(framework_fpath), str(proc_tool_commands_fpath), num_sim_times, sim_time, test_id, str(proc_tool_output_fires_fpath))

    # Generate network SystemVerilog and then bitstream for random network with PYNQ-Z1+petalinux target
    process_network(str(rand_net_json_fpath), str(test_dir_fpath))

if __name__ == '__main__':
    test_pynq_dma(0, 100, 400, 40, 2, 1, 50)