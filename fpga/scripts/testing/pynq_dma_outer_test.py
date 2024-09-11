import subprocess
import pathlib as pl
from periphery import Serial
from network_gen import generate_network
from input_gen import gen_inputs
from pynq_dma_hw_gen import process_network

FRAMEWORK_REL_PATH = "../../../../"
TEST_DIR_REL_PATH_BASE = "test_"
TEMPLATE_NET_REL_PATH = "empty_net_risp.json"
SERIAL_TERMINAL_BAUDRATE = 115200

def test_pynq_dma(test_id: int, num_neurons: int, num_synapses: int, num_inputs: int, num_outputs: int, num_sim_times: int, sim_time: int, zynq_host: str, zynq_serial_device: str, zynq_password: str) -> None:

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
    # template_net_json_fpath = pl.Path(str(this_script_fpath.parent) + "/" + TEMPLATE_NET_REL_PATH)
    # rand_net_json_fpath = pl.Path(str(test_dir_fpath) + "/net.json")
    # generate_network(str(template_net_json_fpath), str(framework_fpath), num_neurons, num_synapses, test_id, num_inputs, num_outputs, str(rand_net_json_fpath))
    rand_net_json_fpath = pl.Path("/home/bryson/Documents/TENNLab/framework/fpga/networks/xor_noleak.txt")

    # Generate random network input in the form of processor tool commands that are written to a file
    proc_tool_commands_fpath = pl.Path(str(test_dir_fpath) + "/proc_tool_commands.txt")
    proc_tool_output_fires_fpath = pl.Path(str(test_dir_fpath) + "/proc_tool_output_fires_sim.txt")
    gen_inputs(str(rand_net_json_fpath), str(framework_fpath), str(proc_tool_commands_fpath), num_sim_times, sim_time, test_id, str(proc_tool_output_fires_fpath))

    # Generate network SystemVerilog and then bitstream for random network with PYNQ-Z1+petalinux target
    zynq_dma_net_fpath = pl.Path(str(test_dir_fpath) + "/net_zynq_dma.json")
    process_network(str(rand_net_json_fpath), str(zynq_dma_net_fpath), str(test_dir_fpath))

    # Edit processor tool commands file to have the correct network file path
    proc_tool_commands_lines = []
    with open(str(proc_tool_commands_fpath), 'r') as f:
        proc_tool_commands_lines = f.readlines()
    with open(str(proc_tool_commands_fpath), 'w') as f:
        for line in proc_tool_commands_lines:
            if "ml" not in line.lower():
                f.write(line)
            else:
                f.write("ML /home/petalinux/zynq_framework/cpp-apps/networks/" + str(TEST_DIR_REL_PATH_BASE) + str(test_id) + "_" + zynq_dma_net_fpath.name + "\n")

    # Generate .bin file from bitstream
    bash_cmd = '''echo all:\n{\n    ''' + str(test_dir_fpath) + '''/pynq_dma.runs/impl_1/pynq_dma_wrapper.bit\n}\n'''
    with open(str(test_dir_fpath) + "/Full_Bitstream.bif", 'w') as f:
        subprocess.run(bash_cmd.split(' '), stdout=f)
    bash_cmd = "bootgen -image " + str(test_dir_fpath) + "/Full_Bitstream.bif -arch zynq -process_bitstream bin -w"
    subprocess.run(bash_cmd.split(' '))

    # Copy pynq_dma network .bin file, network file, zynq_dma network file, processor tool inputs, and simulated processor tool outputs to zynq over network connection via scp
    # bash_cmd = "mkdir " + str(this_script_fpath.parent) + "/zynq_framework; git -C " + str(framework_fpath) + "archive HEAD | tar -x -C " + str(this_script_fpath.parent) + "/zynq_framework"
    # subprocess.run(bash_cmd.split(' '))
    # bash_cmd = "sshpass -p " + str(zynq_password) + " scp -r " + str(this_script_fpath.parent) + "/zynq_framework petalinux@" + str(zynq_host) + ":/home/petalinux/"
    # subprocess.run(bash_cmd.split(' '))
    bash_cmd = "sshpass -p " + str(zynq_password) + " scp " + str(test_dir_fpath) + "/pynq_dma.runs/impl_1/pynq_dma_wrapper.bit.bin petalinux@" + str(zynq_host) + ":/home/petalinux/network.bit.bin"
    print(bash_cmd)
    subprocess.run(bash_cmd.split(' '))
    bash_cmd = "sshpass -p " + str(zynq_password) + " scp " + str(rand_net_json_fpath) + " petalinux@" + str(zynq_host) + ":/home/petalinux/zynq_framework/cpp-apps/networks/" + str(TEST_DIR_REL_PATH_BASE) + str(test_id) + "_" + rand_net_json_fpath.name
    subprocess.run(bash_cmd.split(' '))
    bash_cmd = "sshpass -p " + str(zynq_password) + " scp " + str(zynq_dma_net_fpath) + " petalinux@" + str(zynq_host) + ":/home/petalinux/zynq_framework/cpp-apps/networks/" + str(TEST_DIR_REL_PATH_BASE) + str(test_id) + "_" + zynq_dma_net_fpath.name
    subprocess.run(bash_cmd.split(' '))
    bash_cmd = "sshpass -p " + str(zynq_password) + " scp " + str(proc_tool_commands_fpath) + " petalinux@" + str(zynq_host) + ":/home/petalinux/"
    subprocess.run(bash_cmd.split(' '))
    bash_cmd = "sshpass -p " + str(zynq_password) + " scp " + str(proc_tool_output_fires_fpath) + " petalinux@" + str(zynq_host) + ":/home/petalinux/"
    subprocess.run(bash_cmd.split(' '))

    # Connect to zynq linux terminal via serial connection
    serial_interface = Serial(zynq_serial_device, SERIAL_TERMINAL_BAUDRATE)

    # Run list of bash commands on zynq from serial terminal
    serial_cmds = [
        "echo " + str(zynq_password) + " | sudo -S bash /home/petalinux/test_new_net.sh",
    ]
    serial_interface.write(bytes(" ; ".join(serial_cmds) + '\n', "utf-8"))
    serial_interface.flush()

    # Get and print output from zynq via serial terminal
    serial_output = ""
    while("NETWORK HARDWARE TEST COMPLETE" not in serial_output):
        new_output = serial_interface.read(100, 4).decode("utf-8")
        if new_output != "":
            print(new_output)
            serial_output += new_output


if __name__ == '__main__':
    test_pynq_dma(0, 100, 400, 40, 2, 2, 50, "10.42.0.128", "/dev/ttyUSB1", "tennlab")