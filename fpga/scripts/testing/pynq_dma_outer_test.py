import re
import subprocess
import pathlib as pl
from periphery import Serial
from network_gen import generate_network
from input_gen import gen_proc_tool_commands_from_net, gen_proc_tool_outputs_from_net_and_commands
from pynq_dma_hw_gen import process_network

FRAMEWORK_REL_PATH = "../../../../"
TEST_DIR_REL_PATH_BASE = "test_"
TEMPLATE_NET_REL_PATH = "empty_net_risp.json"
SERIAL_TERMINAL_BAUDRATE = 115200

# Edit processor tool commands file to have the correct network file path
def proc_tool_commands_file_edit(proc_tool_commands_fpath: pl.Path, test_dir_fpath: pl.Path, net_json_fpath: pl.Path) -> pl.Path:
    if not proc_tool_commands_fpath.is_file():
        raise RuntimeError("proc_tool_commands_file_edit() Given processor tool commands file path, " + str(proc_tool_commands_fpath), + "is invalid")
    if not test_dir_fpath.is_dir():
        raise RuntimeError("proc_tool_commands_file_edit() Given directory, " + str(test_dir_fpath), + "is invalid")
    if not net_json_fpath.is_file():
        raise RuntimeError("proc_tool_commands_file_edit() Given network JSON file path, " + str(net_json_fpath), + "is invalid")

    proc_tool_commands_lines = []
    with open(str(proc_tool_commands_fpath), 'r') as f:
        proc_tool_commands_lines = f.readlines()

    proc_tool_commands_zynq_fpath = pl.Path(str(test_dir_fpath) + "/proc_tool_commands_zynq.txt")
    
    with open(str(proc_tool_commands_zynq_fpath), 'w') as f:
        for line in proc_tool_commands_lines:
            if "ml" not in line.lower():
                f.write(line)
            else:
                f.write("ML /home/petalinux/zynq_framework/cpp-apps/networks/" + test_dir_fpath.stem + "_" + net_json_fpath.name + "\n")

    return proc_tool_commands_zynq_fpath

# Generate .bin file from bitstream
def gen_bin_file(test_dir_fpath: pl.Path) -> None:
    if not test_dir_fpath.is_dir():
        raise RuntimeError("gen_bin_file() Given directory, " + str(test_dir_fpath), + "is invalid")

    bash_cmd = '''echo all:\n{\n    ''' + str(test_dir_fpath) + '''/pynq_dma.runs/impl_1/pynq_dma_wrapper.bit\n}\n'''
    with open(str(test_dir_fpath) + "/Full_Bitstream.bif", 'w') as f:
        subprocess.run(bash_cmd.split(' '), stdout=f)
    bash_cmd = "bootgen -image " + str(test_dir_fpath) + "/Full_Bitstream.bif -arch zynq -process_bitstream bin -w"
    subprocess.run(bash_cmd.split(' '))

# Copy pynq_dma network .bin file, network file, processor tool inputs, and simulated processor tool outputs to zynq over network connection via scp
def copy_test_files_to_zynq(test_dir_fpath: pl.Path, net_json_fpath: pl.Path, proc_tool_commands_fpath: pl.Path, proc_tool_output_fires_fpath: pl.Path, zynq_host: str, zynq_password: str) -> None:
    if not test_dir_fpath.is_dir():
        raise RuntimeError("copy_test_files_to_zynq() Given directory, " + str(test_dir_fpath), + "is invalid")
    if not net_json_fpath.is_file():
        raise RuntimeError("copy_test_files_to_zynq() Given network JSON file path, " + str(net_json_fpath), + "is invalid")
    if not proc_tool_commands_fpath.is_file():
        raise RuntimeError("copy_test_files_to_zynq() Given processor tool commands file path, " + str(proc_tool_commands_fpath), + "is invalid")
    if not proc_tool_output_fires_fpath.is_file():
        raise RuntimeError("copy_test_files_to_zynq() Given processor tool simulated output fires file path, " + str(proc_tool_output_fires_fpath), + "is invalid")

    # bash_cmd = "mkdir " + str(this_script_fpath.parent) + "/zynq_framework; git -C " + str(framework_fpath) + "archive HEAD | tar -x -C " + str(this_script_fpath.parent) + "/zynq_framework"
    # subprocess.run(bash_cmd.split(' '))
    # bash_cmd = "sshpass -p " + str(zynq_password) + " scp -r " + str(this_script_fpath.parent) + "/zynq_framework petalinux@" + str(zynq_host) + ":/home/petalinux/"
    # subprocess.run(bash_cmd.split(' '))
    bash_cmd = "sshpass -p " + str(zynq_password) + " scp " + str(test_dir_fpath) + "/pynq_dma.runs/impl_1/pynq_dma_wrapper.bit.bin petalinux@" + str(zynq_host) + ":/home/petalinux/network.bit.bin"
    print(bash_cmd)
    subprocess.run(bash_cmd.split(' '))
    bash_cmd = "sshpass -p " + str(zynq_password) + " scp " + str(net_json_fpath) + " petalinux@" + str(zynq_host) + ":/home/petalinux/zynq_framework/cpp-apps/networks/" + test_dir_fpath.stem + "_" + net_json_fpath.name
    print(bash_cmd)
    subprocess.run(bash_cmd.split(' '))
    bash_cmd = "sshpass -p " + str(zynq_password) + " scp " + str(proc_tool_commands_fpath) + " petalinux@" + str(zynq_host) + ":/home/petalinux/"
    print(bash_cmd)
    subprocess.run(bash_cmd.split(' '))
    bash_cmd = "sshpass -p " + str(zynq_password) + " scp " + str(proc_tool_output_fires_fpath) + " petalinux@" + str(zynq_host) + ":/home/petalinux/"
    print(bash_cmd)
    subprocess.run(bash_cmd.split(' '))

def run_zynq_test(zynq_serial_device: str, zynq_password: str) -> float:
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

    tot_time_fpga = -1.0
    tot_time_sim_zynq = -1.0
    if "are identical" in serial_output:
        tot_times = re.findall("real\s*(\d*)h?(\d+)m(\d+\.\d+)s", serial_output)
        if len(tot_times) >= 1:
            hours = 0
            if tot_times[0][0] != "":
                hours = float(tot_times[0][0])
            tot_time_fpga = hours*3600.0 + float(tot_times[0][1])*60.0 + float(tot_times[0][2])
        if len(tot_times) >= 2:
            hours = 0
            if tot_times[1][0] != "":
                hours = float(tot_times[1][0])
            tot_time_sim_zynq = hours*3600.0 + float(tot_times[1][1])*60.0 + float(tot_times[1][2])

    run_time_fpga = -1
    run_time_sim_zynq = -1
    if "are identical" in serial_output:
        run_times = re.findall("It took (\d+) sec", serial_output)
        if len(run_times) >= 1:
            run_time_fpga = int(run_times[0])
        if len(run_times) >= 2:
            run_time_sim_zynq = int(run_times[1])

    return int(tot_time_fpga), run_time_fpga, int(tot_time_sim_zynq), run_time_sim_zynq

def test_pynq_dma_rand_net_inp(test_id: int, num_neurons: int, num_synapses: int, num_inputs: int, num_outputs: int, num_sim_times: int, sim_time: int, zynq_host: str, zynq_serial_device: str, zynq_password: str) -> float:

    # Find path to this python file
    this_script_fpath = pl.Path(__file__).resolve()
    if "pynq_dma_outer_test.py" not in str(this_script_fpath):
        raise RuntimeError("Could not resolve the file path for this Python script.")
    
    # Find path to framework
    framework_fpath = pl.Path(str(this_script_fpath.parent) + "/" + FRAMEWORK_REL_PATH)

    # Find path to test directory and create it if necessary
    test_dir_fpath = pl.Path(str(this_script_fpath.parent) + "/" + TEST_DIR_REL_PATH_BASE + str(test_id))
    if not test_dir_fpath.is_dir():
        test_dir_fpath.mkdir(parents=True, exist_ok=True)

    # Generate random network that is written out to a file
    template_net_json_fpath = pl.Path(str(this_script_fpath.parent) + "/" + TEMPLATE_NET_REL_PATH)
    rand_net_json_fpath = pl.Path(str(test_dir_fpath) + "/net.json")
    network_tool_commands_fpath = pl.Path(str(test_dir_fpath) + "/net_tool_commands.txt")
    generate_network(str(template_net_json_fpath), str(framework_fpath), num_neurons, num_synapses, test_id, num_inputs, num_outputs, str(network_tool_commands_fpath), str(rand_net_json_fpath))

    # Generate random network input in the form of processor tool commands that are written to a file
    proc_tool_commands_fpath = pl.Path(str(test_dir_fpath) + "/proc_tool_commands.txt")
    proc_tool_output_fires_fpath = pl.Path(str(test_dir_fpath) + "/proc_tool_output_fires_sim.txt")
    gen_proc_tool_commands_from_net(str(rand_net_json_fpath), str(framework_fpath), str(proc_tool_commands_fpath), num_sim_times, sim_time, test_id)
    gen_proc_tool_outputs_from_net_and_commands(str(rand_net_json_fpath), str(proc_tool_commands_fpath), str(framework_fpath), str(proc_tool_output_fires_fpath))

    # Generate network SystemVerilog and then bitstream for random network with PYNQ-Z1+petalinux target
    if len(list(pl.Path(str(test_dir_fpath) + "/pynq_dma.runs/impl_1/").glob("*.bit"))) == 0:
        process_network(str(rand_net_json_fpath), str(test_dir_fpath))

    proc_tool_commands_zynq_fpath = proc_tool_commands_file_edit(proc_tool_commands_fpath, test_dir_fpath, rand_net_json_fpath)

    # Generate network SystemVerilog and then bitstream for random network with PYNdet_AI
    gen_bin_file(test_dir_fpath)

    copy_test_files_to_zynq(test_dir_fpath, rand_net_json_fpath, proc_tool_commands_zynq_fpath, proc_tool_output_fires_fpath, zynq_host, zynq_password)

    return run_zynq_test(zynq_serial_device, zynq_password)

def test_pynq_dma_rand_inp(test_id: int, net_json_path: str, num_sim_times: int, sim_time: int, zynq_host: str, zynq_serial_device: str, zynq_password: str) -> float:

    # Find path to this python file
    this_script_fpath = pl.Path(__file__).resolve()
    if "pynq_dma_outer_test.py" not in str(this_script_fpath):
        raise RuntimeError("Could not resolve the file path for this Python script.")
    
    # Find path to framework
    framework_fpath = pl.Path(str(this_script_fpath.parent) + "/" + FRAMEWORK_REL_PATH)

    # Find path to desired test network
    net_json_fpath = pl.Path(net_json_path).resolve()
    if not net_json_fpath.is_file():
        raise RuntimeError("Could not resolve the given network JSON path, " + str(net_json_path))

    # Find path to test directory and create it if necessary
    test_dir_fpath = pl.Path(str(this_script_fpath.parent) + "/" + TEST_DIR_REL_PATH_BASE + str(test_id) + "_" + net_json_fpath.stem)
    if not test_dir_fpath.is_dir():
        test_dir_fpath.mkdir(parents=True, exist_ok=True)

    # Generate random network input in the form of processor tool commands that are written to a file
    proc_tool_commands_fpath = pl.Path(str(test_dir_fpath) + "/proc_tool_commands.txt")
    proc_tool_output_fires_fpath = pl.Path(str(test_dir_fpath) + "/proc_tool_output_fires_sim.txt")
    gen_proc_tool_commands_from_net(str(net_json_fpath), str(framework_fpath), str(proc_tool_commands_fpath), num_sim_times, sim_time, test_id)
    gen_proc_tool_outputs_from_net_and_commands(str(net_json_fpath), str(proc_tool_commands_fpath), str(framework_fpath), str(proc_tool_output_fires_fpath))

    # Generate network SystemVerilog and then bitstream for random network with PYNQ-Z1+petalinux target
    if len(list(pl.Path(str(test_dir_fpath) + "/pynq_dma.runs/impl_1/").glob("*.bit"))) == 0:
        process_network(str(net_json_fpath), str(test_dir_fpath))

    proc_tool_commands_zynq_fpath = proc_tool_commands_file_edit(proc_tool_commands_fpath, test_dir_fpath, net_json_fpath)

    gen_bin_file(test_dir_fpath)

    copy_test_files_to_zynq(test_dir_fpath, net_json_fpath, proc_tool_commands_zynq_fpath, proc_tool_output_fires_fpath, zynq_host, zynq_password)

    return run_zynq_test(zynq_serial_device, zynq_password)

def test_pynq_dma(test_id: int, net_json_path: str, proc_tool_commands_path: str, zynq_host: str, zynq_serial_device: str, zynq_password: str) -> float:

    # Find path to this python file
    this_script_fpath = pl.Path(__file__).resolve()
    if "pynq_dma_outer_test.py" not in str(this_script_fpath):
        raise RuntimeError("Could not resolve the file path for this Python script.")
    
    # Find path to framework
    framework_fpath = pl.Path(str(this_script_fpath.parent) + "/" + FRAMEWORK_REL_PATH)

    # Find path to desired test network
    net_json_fpath = pl.Path(net_json_path).resolve()
    if not net_json_fpath.is_file():
        raise RuntimeError("Could not resolve the given network JSON path, " + str(net_json_path))
    
    # Find path to desired test processor tool commands file
    proc_tool_commands_fpath = pl.Path(proc_tool_commands_path).resolve()
    if not proc_tool_commands_fpath.is_file():
        raise RuntimeError("Could not resolve the given processor too commands file path, " + str(proc_tool_commands_path))

    # Find path to test directory and create it if necessary
    test_dir_fpath = pl.Path(str(this_script_fpath.parent) + "/" + TEST_DIR_REL_PATH_BASE + str(test_id) + "_" + net_json_fpath.stem)
    if not test_dir_fpath.is_dir():
        test_dir_fpath.mkdir(parents=True, exist_ok=True)

    # Generate processor tool outputs from given processor tool input commands file
    proc_tool_output_fires_fpath = pl.Path(str(test_dir_fpath) + "/proc_tool_output_fires_sim.txt")
    gen_proc_tool_outputs_from_net_and_commands(str(net_json_fpath), str(proc_tool_commands_fpath), str(framework_fpath), str(proc_tool_output_fires_fpath))

    # Generate network SystemVerilog and then bitstream for random network with PYNQ-Z1+petalinux target
    if len(list(pl.Path(str(test_dir_fpath) + "/pynq_dma.runs/impl_1/").glob("*.bit"))) == 0:
        process_network(str(net_json_fpath), str(test_dir_fpath))

    proc_tool_commands_zynq_fpath = proc_tool_commands_file_edit(proc_tool_commands_fpath, test_dir_fpath, net_json_fpath)

    gen_bin_file(test_dir_fpath)

    copy_test_files_to_zynq(test_dir_fpath, net_json_fpath, proc_tool_commands_zynq_fpath, proc_tool_output_fires_fpath, zynq_host, zynq_password)

    return run_zynq_test(zynq_serial_device, zynq_password)

if __name__ == '__main__':

    # test_pynq_dma_rand_inp(124, "/home/bryson/Documents/TENNLab/framework/fpga/networks/dbscan_systolic_346_2_4.json", 20, 10000, "10.42.0.128", "/dev/ttyUSB1", "tennlab")

    ptool_fpaths = pl.Path("/home/bryson/Desktop/generated_data_ptool_cmds").glob('*')

    t_id = 0
    with open("gen_data_dbscan_systolic_346_times.csv", 'a') as times_file:
        for ptool_fpath in ptool_fpaths:

            print(str(ptool_fpath))

            proc_tool_commands_lines = []
            with open(str(ptool_fpath), 'r') as ptool_file:
                proc_tool_commands_lines = ptool_file.readlines()

            with open(str(ptool_fpath), 'w') as ptool_file:
                for line in proc_tool_commands_lines:
                    if "ml" not in line.lower():
                        ptool_file.write(line)
                    else:
                        ptool_file.write("ML /home/bryson/Documents/TENNLab/framework/fpga/networks/dbscan_systolic_346_2_4.json\n")
            tot_time_fpga, run_time_fpga, tot_time_sim_zynq, run_time_sim_zynq = test_pynq_dma(124, "/home/bryson/Documents/TENNLab/framework/fpga/networks/dbscan_systolic_346_2_4.json", str(ptool_fpath), "10.42.0.128", "/dev/ttyUSB1", "tennlab")

            bash_cmd = "time /home/bryson/Documents/TENNLab/framework/cpp-apps/bin/processor_tool_risp"
            with open(str(ptool_fpath), 'r') as ptool_file:
                p = subprocess.run(bash_cmd.split(' '), stdin=ptool_file, capture_output=True)

            tot_time_sim_pangolin = int(float(re.findall("(\d+\.\d+)user", p.stderr.decode())[0]))
            run_time_sim_pangolin = int(re.findall("It took (\d+) sec", p.stderr.decode())[0])

            times_file.write(f"{t_id}, {ptool_fpath}, {tot_time_fpga}, {run_time_fpga}, {tot_time_sim_zynq}, {run_time_sim_zynq}, {tot_time_sim_pangolin}, {run_time_sim_pangolin}\n")
            times_file.flush()

            t_id += 1